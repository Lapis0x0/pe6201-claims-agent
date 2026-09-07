"""Reproduce D2(b)'s descriptor, observation-size and guardrail controls.

This is deliberately zero-cost.  The v1 live arm changed only the descriptor;
the runtime ``check_coverage`` implementation was held fixed.  Consequently
the actual observation returned for the same lookup is identical in both arms.
That null result is important: the measured live difference is attributable to
the descriptor, not to a silently changed tool implementation.
"""

import math
import statistics

import config
import descriptors_v1
from guardrail_checklist import build_rows
from tools import ClaimsTools, load_table


def approx_tokens(text):
    """Repository-wide transparent estimate used for static text controls."""
    return math.ceil(len(text) / 4)


def observation_measurement():
    claim = load_table("claims")[0]
    tool = ClaimsTools(claim)
    observations = [
        tool.check_coverage(policy["policy_id"], procedure["code"])
        for policy in tool.policies
        for procedure in tool.procedures
    ]
    chars = [len(value) for value in observations]
    tokens = [approx_tokens(value) for value in observations]
    return {
        "lookups": len(observations),
        "min_chars": min(chars),
        "median_chars": statistics.median(chars),
        "max_chars": max(chars),
        "mean_chars": statistics.mean(chars),
        "min_tokens": min(tokens),
        "median_tokens": statistics.median(tokens),
        "max_tokens": max(tokens),
        "mean_tokens": statistics.mean(tokens),
    }


def main():
    v1 = config.render_tool_list(descriptors_v1.OVERRIDES)
    v2 = config.render_tool_list()
    obs = observation_measurement()
    guardrails = build_rows()
    passed = sum(row["passed"] for row in guardrails)

    print("D2(b) zero-cost control measurement")
    print("descriptor tokens: v1={} v2={} delta={:+d}".format(
        approx_tokens(v1), approx_tokens(v2),
        approx_tokens(v2) - approx_tokens(v1)))
    print(
        "actual check_coverage observations ({} fixture-valid lookups): "
        "chars min/median/max={}/{:.0f}/{}, mean={:.2f}; "
        "estimated tokens min/median/max={}/{:.0f}/{}, mean={:.2f}".format(
            obs["lookups"], obs["min_chars"], obs["median_chars"],
            obs["max_chars"], obs["mean_chars"], obs["min_tokens"],
            obs["median_tokens"], obs["max_tokens"], obs["mean_tokens"]
        )
    )
    print("observation-size comparison: v1 = v2 (runtime tool held fixed)")
    print("guardrail checklist: v1={0}/{1}; v2={0}/{1} (code held fixed)".format(
        passed, len(guardrails)))

    assert passed == len(guardrails)


if __name__ == "__main__":
    main()
