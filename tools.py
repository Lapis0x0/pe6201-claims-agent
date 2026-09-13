"""The tool layer for the Problem A claims agent.

Every tool reads the local fixture data in data_A/ and returns a formatted
string: the observation the model reads. Nothing here returns a raw dict,
because the model never sees a dict.

The signatures, argument names and returned-observation shapes are the shipped
contract shared by the agent and system prompt. Any future signature change
must also update config.TOOL_SPECS and the scripted trajectories in
scripts_A.py.

One tool owns state: issue_decision_letter. It is the gated action, and the
gate needs to know what happened earlier in the run, so the tools are bound to
a per-run ClaimsTools instance rather than being free functions.
"""

import json
import os
import re
from datetime import datetime, timezone

import config


# ---------------------------------------------------------------------------
# data loading
# ---------------------------------------------------------------------------

def load_table(name, data_dir=config.DATA_DIR):
    """Load one fixture table by file name (without .json)."""
    with open(os.path.join(data_dir, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def _first(rows, **match):
    """Return the first row whose fields all equal the given values, or None."""
    for row in rows:
        if all(row.get(key) == value for key, value in match.items()):
            return row
    return None


def _money(value):
    return "{:,.0f}".format(value)


def _collapse_evidence(calls):
    """["check_coverage","check_coverage","check_hospital"] ->
    ["check_coverage x2","check_hospital"] - one entry per tool, in the
    order it was first called, matching the brief's own worked-example
    shape ("check_coverage x3")."""
    seen = []
    counts = {}
    for name in calls:
        if name not in counts:
            seen.append(name)
        counts[name] = counts.get(name, 0) + 1
    return [
        name if counts[name] == 1 else "{} x{}".format(name, counts[name])
        for name in seen
    ]


# ---------------------------------------------------------------------------
# the tools
# ---------------------------------------------------------------------------

class ClaimsTools:
    """One instance per agent run.

    The instance holds the fixture tables, the claim under assessment, and the
    small amount of run state the autonomy gate needs.

    `autonomy` selects which of config.AUTONOMY_SETTINGS the decision gate
    enforces (D3a). `operator_approved` simulates whatever a real deployment
    would use to know a human has signed off on THIS claim's proposed
    decision - a dashboard click, a Slack approval, and so on. There is no
    UI in this system (out of scope, D1), so it is a constructor argument:
    the harness and the normal evaluation runs pass True (a human has
    already reviewed, which is the ordinary case this system is built for);
    D3(b)'s guardrail checklist passes False for exactly one case, to prove
    the gate actually blocks when that hasn't happened.
    """

    def __init__(self, claim, data_dir=config.DATA_DIR,
                 decisions_path=config.DECISIONS_PATH,
                 autonomy=config.AUTONOMY, operator_approved=True,
                 return_shape_version="v1"):
        self.claim = claim
        self.decisions_path = decisions_path
        self.autonomy = autonomy
        self.operator_approved = operator_approved
        # D2(b) return-shape control arm: v1 is the original prose sentence
        # (below, unchanged); v2 is a typed JSON string for check_coverage
        # only, holding the descriptor fixed at config.TOOL_SPECS v2 so the
        # return shape is the only variable that moves. See
        # docs/d2b_return_shape.md.
        self.return_shape_version = return_shape_version
        self.members = load_table("members", data_dir)
        self.policies = load_table("policies", data_dir)
        self.procedures = load_table("procedures", data_dir)
        self.hospitals = load_table("hospitals", data_dir)
        self.preauthorisations = load_table("preauthorisations", data_dir)
        self.required_documents = load_table("required_documents", data_dir)
        self.decided_claims = load_table("decided_claims", data_dir)

        # run state, read by the gate
        self.policy_looked_up = False
        self.letter_issued = False

        # D1 audit trail, read by issue_decision_letter when it writes the
        # record. ToolLayer has no visibility into turns or backend cost by
        # itself, so the agent loop populates these three right before
        # dispatching issue_decision_letter (agent.py's _dispatch and
        # _current_cost).
        self.evidence_calls = []
        self.turn = 0
        self.cost_so_far = 0.0

    # -- registry ----------------------------------------------------------

    def as_dict(self):
        """The {name: callable} mapping the agent loop dispatches on."""
        return {
            "lookup_member_policy": self.lookup_member_policy,
            "check_coverage": self.check_coverage,
            "get_preauthorisation": self.get_preauthorisation,
            "check_hospital": self.check_hospital,
            "check_duplicate": self.check_duplicate,
            "issue_decision_letter": self.issue_decision_letter,
        }

    # -- read-only tools ---------------------------------------------------

    def lookup_member_policy(self, member_id):
        """Return the member and their policy in one hop.

        Two lookups (members -> policies) are collapsed into one tool because
        the member row carries nothing the agent needs except the policy id.

        Args:
            member_id: e.g. "M-2214".

        Returns:
            A formatted observation carrying policy status, validity dates,
            annual limit, amount used, remaining limit and exclusions.
        """
        member = _first(self.members, member_id=member_id)
        if member is None:
            return "NOT FOUND: no member with member_id {}.".format(member_id)
        self.policy_looked_up = True
        policy = _first(self.policies, policy_id=member["policy_id"])
        if policy is None:
            return (
                "NOT FOUND: member {} points at policy {} which does not "
                "exist.".format(member_id, member["policy_id"])
            )

        # Pre-computed so the model never has to do the subtraction itself.
        remaining = policy["annual_limit"] - policy["used_to_date"]
        if policy["exclusions"]:
            exclusions = "; ".join(
                "{code} ({rule})".format(**e) for e in policy["exclusions"]
            )
        else:
            exclusions = "(none)"
        return (
            "member {member_id} ({name}) holds policy {policy_id} ({product}). "
            "status: {status}. valid from {start_date} to {end_date}. "
            "annual limit {limit}, used to date {used}, remaining {remaining}. "
            "exclusions: {exclusions}".format(
                member_id=member["member_id"], name=member["name"],
                policy_id=policy["policy_id"], product=policy["product"],
                status=policy["status"], start_date=policy["start_date"],
                end_date=policy["end_date"], limit=_money(policy["annual_limit"]),
                used=_money(policy["used_to_date"]),
                remaining=_money(remaining), exclusions=exclusions,
            )
        )

    def check_coverage(self, policy_id, procedure_code):
        """Return the coverage position for one procedure on one policy.

        Deliberately one line item per call: a multi-line claim cannot be
        answered from a single lookup, so the agent has to work the lines.

        Args:
            policy_id:      e.g. "POL-3310".
            procedure_code: e.g. "47120".

        Returns:
            A formatted observation naming exclusion status and rule,
            pre-authorisation requirement, and required supporting document.
        """
        v2 = self.return_shape_version == "v2"
        policy = _first(self.policies, policy_id=policy_id)
        if policy is None:
            if v2:
                return json.dumps({"error": "NOT FOUND", "field": "policy_id",
                                    "value": policy_id})
            return "NOT FOUND: no policy with policy_id {}.".format(policy_id)
        procedure = _first(self.procedures, code=procedure_code)
        if procedure is None:
            if v2:
                return json.dumps({"error": "NOT FOUND", "field": "procedure_code",
                                    "value": procedure_code})
            return "NOT FOUND: no procedure with code {}.".format(procedure_code)

        exclusion = _first(policy["exclusions"], code=procedure_code)
        required = _first(self.required_documents, procedure_code=procedure_code)
        if v2:
            return json.dumps({
                "policy_id": policy_id,
                "procedure_code": procedure["code"],
                "description": procedure["description"],
                "covered": exclusion is None,
                "exclusion_rule": exclusion["rule"] if exclusion else None,
                "requires_preauth": bool(procedure["requires_preauth"]),
                "required_document": required["document"] if required else None,
            })
        if exclusion is None:
            covered = "covered by {}".format(policy_id)
        else:
            covered = "EXCLUDED by {} under {}".format(policy_id, exclusion["rule"])
        return (
            "procedure {code} ({description}): {covered}. "
            "requires_preauth: {preauth}. required_document: {document}".format(
                code=procedure["code"], description=procedure["description"],
                covered=covered,
                preauth="yes" if procedure["requires_preauth"] else "no",
                document=required["document"] if required else "none",
            )
        )

    def get_preauthorisation(self, member_id, procedure_code, date_of_service):
        """Return the pre-authorisation for a member and procedure.

        date_of_service is required, not optional: an authorisation that exists
        is not an authorisation that applies, and making the date mandatory
        means validity is always evaluated.

        Args:
            member_id:       e.g. "M-2214".
            procedure_code:  e.g. "62480".
            date_of_service: ISO date, e.g. "2026-09-02".

        Returns:
            A formatted observation stating whether a record exists and whether
            it was valid on the date of service.
        """
        record = _first(self.preauthorisations, member_id=member_id,
                        procedure_code=procedure_code)
        if record is None:
            return (
                "NO RECORD: member {} has no pre-authorisation on file for "
                "procedure {}.".format(member_id, procedure_code)
            )
        # ISO dates compare correctly as strings.
        valid = record["valid_from"] <= date_of_service <= record["valid_to"]
        return (
            "{preauth_id}: member {member_id}, procedure {procedure_code}, "
            "valid from {valid_from} to {valid_to}. On date of service "
            "{date_of_service} this authorisation is {verdict}.".format(
                date_of_service=date_of_service,
                verdict="VALID" if valid else "NOT VALID (outside its window)",
                **record
            )
        )

    def check_hospital(self, hospital_id):
        """Return the hospital record including panel status.

        Args:
            hospital_id: e.g. "H-114".

        Returns:
            A formatted observation. Panel status is always stated explicitly.
        """
        hospital = _first(self.hospitals, hospital_id=hospital_id)
        if hospital is None:
            return "NOT FOUND: no hospital with hospital_id {}.".format(hospital_id)
        return (
            "hospital {hospital_id} ({name}, {country}): panel status "
            "{panel}.".format(
                hospital_id=hospital["hospital_id"], name=hospital["name"],
                country=hospital["country"],
                panel="ON PANEL" if hospital["panel"] else "NON-PANEL",
            )
        )

    def check_duplicate(self, member_id, hospital_id, date_of_service, lines):
        """Look for an already-decided claim matching on all four facts.

        All four are required arguments and all four must match. The claims
        history holds deliberate near-misses, so a three-field comparison finds
        false duplicates.

        Args:
            member_id:       e.g. "M-2214".
            hospital_id:     e.g. "H-114".
            date_of_service: ISO date.
            lines:           the claim's line items, [{"code", "amount"}, ...].

        Returns:
            A formatted observation naming the prior claim, or NO MATCH.
        """
        wanted = _line_key(lines)
        for prior in self.decided_claims:
            if (prior["member_id"] == member_id
                    and prior["hospital_id"] == hospital_id
                    and prior["date_of_service"] == date_of_service
                    and _line_key(prior["lines"]) == wanted):
                return (
                    "MATCH: claim {claim_id} was already decided "
                    "({decision}) on {decided_on}. It matches on all four "
                    "facts: member {member_id}, hospital {hospital_id}, date "
                    "of service {date_of_service}, and identical line "
                    "items.".format(**prior)
                )
        return (
            "NO MATCH: no decided claim matches all four of member {}, "
            "hospital {}, date of service {} and these line items. Any prior "
            "claim sharing only some of these facts is a different "
            "claim.".format(member_id, hospital_id, date_of_service)
        )

    # -- the gated action --------------------------------------------------

    def issue_decision_letter(self, claim_id, decision, detail):
        """GATED, IRREVERSIBLE. Record the first-response decision.

        Three steps, in this order:
          1. check the gate;
          2. append one structured record to decisions.jsonl;
          3. return the confirmation string.

        The gate refuses rather than raises, so a refusal reaches the model as
        an observation it can act on.

        The record carries a full audit trail alongside the decision itself -
        timestamp, the evidence trail, the autonomy setting, gate/approval
        status, the turn it was recorded on, and the run's cost so far - so
        decisions.jsonl answers "which decision, on what evidence, after
        which gate, and at what cost" on its own, matching the brief's D1
        worked example, without needing the harness's separate AgentResult.
        cost_usd is computed by agent.py's _current_cost() from
        config.PRICE_PER_MILLION (the single pricing source this project
        also uses for harness.py's own reporting) at the moment of the
        write, and is 0.0 on the scripted backend or any unpriced model.

        Args:
            claim_id: the claim being decided.
            decision: one of config.DECISIONS.
            detail:   the supporting record. Required fields depend on the
                      decision; see check_decision_gate.

        Returns:
            "RECORDED ..." on success, or "GATE REFUSED: ..." with the reason.
        """
        refusal = self.check_decision_gate(claim_id, decision, detail)
        if refusal is not None:
            return "GATE REFUSED: " + refusal

        if self.autonomy == "confirm":
            gate_status = "operator approved at turn {}".format(self.turn)
        else:
            gate_status = (
                "autonomy={}, no operator confirmation required".format(
                    self.autonomy)
            )

        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "claim_id": claim_id,
            "decision": decision,
            "detail": detail,
            "evidence": _collapse_evidence(self.evidence_calls),
            "autonomy": self.autonomy,
            "gate": gate_status,
            "turns": self.turn,
            "cost_usd": round(self.cost_so_far, 4),
        }
        with open(self.decisions_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.letter_issued = True
        return (
            "RECORDED: decision letter for {} filed as {}. This action is "
            "irreversible; do not call it again for this claim. Give your "
            "Final Answer now.".format(claim_id, decision)
        )

    @staticmethod
    def _substantive(text):
        """True if `text` is a real explanatory string, not a bare token.

        D4's judgement check (docs/d4_judgement_checks.md) found that once a
        gate rule only checks for an id's PRESENCE, a model can satisfy it
        with the id and nothing else ("basis": "PA-5521") - worse prose than
        an unconstrained model would write on its own. This closes that
        specific gap: a citation must sit inside a sentence, not stand alone.
        """
        if not text or not isinstance(text, str):
            return False
        text = text.strip()
        if len(text) < 20:
            return False
        return len(text.split()) >= 5

    def check_decision_gate(self, claim_id, decision, detail):
        """Return a refusal reason, or None if the write may proceed.

        Kept separate from the write so the guardrail checklist (D3b) can
        exercise the gate without touching the file.
        """
        if self.letter_issued:
            return (
                "a decision letter has already been issued in this run. The "
                "action is irreversible and runs at most once."
            )
        if claim_id != self.claim["claim_id"]:
            return (
                "claim_id {} is not the claim under assessment ({}).".format(
                    claim_id, self.claim["claim_id"])
            )
        if decision not in config.DECISIONS:
            return (
                "{!r} is not a decision. Allowed: {}.".format(
                    decision, ", ".join(config.DECISIONS))
            )
        if self.autonomy == "suggest":
            return (
                "autonomy is 'suggest': this system may only recommend a "
                "decision. A human must record it themselves; "
                "issue_decision_letter cannot be called in this mode."
            )
        if self.autonomy == "confirm" and not self.operator_approved:
            return (
                "autonomy is 'confirm': no operator has approved this "
                "claim's decision yet. The write is blocked until they do."
            )
        if not self.policy_looked_up:
            return (
                "the policy has not been looked up in this run. A decision "
                "letter must rest on the policy record."
            )
        if not isinstance(detail, dict):
            return "detail must be a JSON object."

        if decision == "escalate":
            trigger = detail.get("trigger")
            if trigger not in config.ESCALATION_TRIGGERS:
                return (
                    "an escalation must name a known trigger. Got {!r}; "
                    "allowed: {}.".format(
                        trigger, ", ".join(config.ESCALATION_TRIGGERS))
                )
            # D4's judgement check found that a structurally-valid escalation
            # can still name no evidence at all: {"trigger": "..."} alone
            # satisfies the check above. These two poka-yoke rules close that
            # gap in code rather than asking the model to "explain more" -
            # they were found by measuring, not guessed at. See
            # docs/d4_judgement_checks.md.
            if trigger == "instruction_in_member_narrative":
                if not detail.get("injection_found") or not detail.get("action_taken"):
                    return (
                        "an instruction_in_member_narrative escalation must carry "
                        "injection_found (the specific text found in the "
                        "narrative) and action_taken (confirming it was NOT "
                        "followed)."
                    )
                # Re-measurement (docs/d4_judgement_checks.md) found this
                # trigger's own escalations still failed judgement for a
                # third reason beyond the two fields above: no basis at all,
                # so nothing described what the underlying evidence actually
                # showed once the injection was set aside. The shipped
                # scripted trajectories for this trigger already carry a
                # basis field (scripts_A.py) - this makes that the floor for
                # every model, not just the scripted one.
                basis = detail.get("basis")
                if not self._substantive(basis):
                    return (
                        "an instruction_in_member_narrative escalation must "
                        "also carry a basis describing what the real evidence "
                        "showed, not just that the instruction was ignored."
                    )
            else:
                basis = detail.get("basis")
                if not self._substantive(basis):
                    return (
                        "an escalation must carry a basis explaining what was "
                        "found, in a real sentence - not just the trigger "
                        "name, and not a bare id with no surrounding "
                        "explanation."
                    )
                citation = {
                    "policy_lapsed": r"POL-\d+",
                    "outside_policy_dates": r"POL-\d+",
                    "annual_limit_exceeded": r"POL-\d+",
                    "duplicate_claim": r"CLM-\d+",
                }.get(trigger)
                if citation and not re.search(citation, basis):
                    return (
                        "the basis for trigger {!r} must cite the specific "
                        "record it rests on (matching {}), not a general "
                        "description.".format(trigger, citation)
                    )
                if trigger == "duplicate_claim":
                    cited = re.search(r"CLM-\d+", basis).group()
                    prior = next(
                        (c for c in self.decided_claims
                         if c["claim_id"] == cited), None)
                    if prior is None:
                        return (
                            "the basis cites {} but no such decided claim "
                            "exists - cite the actual prior claim.".format(cited)
                        )
                    # The judgement check's own finding: naming the prior
                    # claim id is not the same as naming WHICH facts matched.
                    # Cross-check against the cited claim's own record rather
                    # than guessing what "enough" prose looks like.
                    matched = sum([
                        prior["member_id"] in basis,
                        prior["hospital_id"] in basis,
                        prior["date_of_service"] in basis,
                    ])
                    if matched < 2:
                        return (
                            "the basis names {} but not which facts matched "
                            "it (member, hospital, date of service) - name at "
                            "least two.".format(cited)
                        )
            return None

        if decision == "request_document":
            for field in ("missing_document", "line"):
                if not detail.get(field):
                    return (
                        "a request_document must name {}. The claimant cannot "
                        "act on a request that does not say what is "
                        "missing.".format(field)
                    )
            # Same D4 gap as escalate: missing_document/line alone can be
            # structurally complete ("pre-authorisation", "62480") while
            # explaining nothing about WHY the existing evidence doesn't
            # count - an expired PA and an absent PA look identical to a
            # code check but are different facts to a reader.
            if not self._substantive(detail.get("basis")):
                return (
                    "a request_document must also carry a basis explaining "
                    "why the existing evidence does not satisfy this line - "
                    "not just naming the missing item."
                )
            return None

        # approve_in_principle
        dispositions = detail.get("line_dispositions")
        if not isinstance(dispositions, list) or not dispositions:
            return "an approval must carry line_dispositions."
        decided = {str(d.get("code")) for d in dispositions if isinstance(d, dict)}
        filed = {str(line["code"]) for line in self.claim["lines"]}
        missing = sorted(filed - decided)
        if missing:
            return (
                "every line item needs a disposition. No disposition for: "
                "{}.".format(", ".join(missing))
            )
        for field in ("approved_total", "refused_total"):
            if not isinstance(detail.get(field), (int, float)):
                return "an approval must carry a numeric {}.".format(field)
        # Same D4 finding, applied to approvals: a disposition's basis passed
        # this gate with generic prose ("covered by policy") that named no
        # specific record. Cross-check against the claim's own procedure data
        # instead of sniffing the model's wording for keywords.
        proc_lookup = {p["code"]: p for p in self.procedures}
        date_of_service = self.claim.get("date_of_service", "")
        for d in dispositions:
            if not isinstance(d, dict):
                continue
            code = str(d.get("code"))
            basis = str(d.get("basis", ""))
            proc = proc_lookup.get(code)
            if d.get("disposition") == "approved" and proc and proc.get("requires_preauth"):
                if not re.search(r"PA-\d+", basis):
                    return (
                        "line {} required pre-authorisation; its basis must "
                        "cite the specific PA reference, not just say it is "
                        "covered.".format(code)
                    )
                # A bare id ("basis": "PA-5521") passed the check above while
                # never confirming the authorisation actually covers this
                # claim's date of service - exactly the gap D4's judgement
                # check found live. Require the claim's own date to appear
                # alongside the citation, not just the citation.
                if date_of_service and date_of_service not in basis:
                    return (
                        "line {} cites a PA reference but never confirms it "
                        "covers this claim's date of service ({}).".format(
                            code, date_of_service)
                    )
            if d.get("disposition") == "refused":
                if not re.search(r"EX-\d+", basis):
                    # Found live: a model that tries to refuse a line for a
                    # missing/expired pre-authorisation (rather than an
                    # exclusion) got this refusal, could not resolve it, and
                    # escalated via the loop-control gate rather than
                    # recovering. A within-approval line refusal is only
                    # ever an exclusion in this domain - a missing
                    # authorisation means the whole claim needs
                    # request_document, not a partial refusal - so say that
                    # explicitly instead of just naming what is missing.
                    return (
                        "line {} was refused, but its basis names no "
                        "exclusion code. A line can only be refused inside "
                        "an approval for an exclusion (cite the EX- code). "
                        "If this line lacks a required pre-authorisation or "
                        "document instead, the whole claim needs decision "
                        "request_document, not a partial refusal here - "
                        "call issue_decision_letter again with "
                        "request_document if that is the case.".format(code)
                    )
                if not self._substantive(basis):
                    return (
                        "line {}'s exclusion code needs a real sentence "
                        "around it (what the exclusion is), not a bare "
                        "code.".format(code)
                    )
        return None


def _line_key(lines):
    """A comparable, order-independent key for a set of line items."""
    return sorted((str(line["code"]), line["amount"]) for line in lines)
