"""Zero-cost null control for D2(b)'s return-shape arm.

The live return-shape comparison changes what check_coverage() returns (v1
prose vs v2 typed JSON) while holding the descriptor fixed at config
TOOL_SPECS v2 in both arms. This script proves the descriptor really is
identical in both arms by rendering it once - there is nothing to compare,
which is the point - and measures the actual size delta between the two
return shapes over every fixture-valid lookup, the same way
measure_d2b.py does for the descriptor arm.
"""

import math
import statistics

import config
from tools import ClaimsTools, load_table


def approx_tokens(text):
    return math.ceil(len(text) / 4)


def shape_measurement(version):
    claim = load_table("claims")[0]
    tool = ClaimsTools(claim, return_shape_version=version)
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
    descriptor = config.render_tool_list()
    v1 = shape_measurement("v1")
    v2 = shape_measurement("v2")

    print("D2(b) return-shape zero-cost control measurement")
    print("descriptor tokens: {} (identical in both arms, v2 pinned "
          "throughout)".format(approx_tokens(descriptor)))
    for label, m in (("v1 (prose)", v1), ("v2 (typed JSON)", v2)):
        print(
            "{} — {} lookups: chars min/median/max={}/{:.0f}/{}, "
            "mean={:.2f}; estimated tokens min/median/max={}/{:.0f}/{}, "
            "mean={:.2f}".format(
                label, m["lookups"], m["min_chars"], m["median_chars"],
                m["max_chars"], m["mean_chars"], m["min_tokens"],
                m["median_tokens"], m["max_tokens"], m["mean_tokens"]
            )
        )
    print("token delta (v2 - v1), mean: {:+.2f}".format(
        v2["mean_tokens"] - v1["mean_tokens"]))


if __name__ == "__main__":
    main()
