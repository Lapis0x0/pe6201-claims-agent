"""D2(b) — the v1 descriptor, deliberately worse than v2.

The brief's D2(b) asks for a measured rewrite: ship a v1 and a v2 of one
tool's descriptor and return shape, run v1 on ONE model (the cheap tier),
and quote it against v2 on that same model. The point being measured is
Class 4's own: a prompt instruction is paid for on every call of every run
forever; an interface constraint is paid once and holds.

`check_coverage` is the target because it is called once per line item, so
its descriptor's cost compounds with claim size more than any other tool's.

v1 (below) is what the descriptor looked like before the D2(b) rewrite in
config.TOOL_SPECS: vague about what it uniquely answers, no size bound, no
named failure conditions, and no poka-yoke. v2 is the current entry in
config.TOOL_SPECS — see d2b_descriptor_rewrite.md for the write-up and the
(pending) measured comparison.

Usage: `python3 harness.py --live --model <cheap-tier model> --descriptor-version v1`
swaps this in for check_coverage; `--descriptor-version v2` (the default)
uses config.TOOL_SPECS unchanged. Both must run on the SAME model to isolate
the descriptor as the only variable — see D4's run table.
"""

CHECK_COVERAGE_V1 = {
    "name": "check_coverage",
    "signature": "check_coverage(policy_id, procedure_code)",
    "what": "",
    "input": "policy_id and procedure_code.",
    "returns": "coverage details for the procedure.",
    "fails_when": "the inputs are wrong.",
    "irreversible": "No.",
    "poka_yoke": [],
    "prompt_guidance": "use this to check coverage.",
}

# What run_evaluation()/ClaimsAgent pass into config.render_tool_list().
OVERRIDES = {
    "check_coverage": CHECK_COVERAGE_V1,
}
