"""D7's loop-control failure, worked once, for the demo video.

Same evidence as `failure1_loop.py` (that file is what the report's numbers
come from) - this is a narrated, presentation-friendly wrapper around it,
matching the shape of the professor's own scaffold demo
(`A2_scaffold/demo_loop_failure.py`). No logic lives here; everything is
imported.

Usage: python3 demo_loop_failure.py
"""

import config
import failure1_loop


def main():
    print("=" * 72)
    print("D7 - Failure 1: a loop-control failure that raises no exception")
    print("=" * 72)
    print()
    print("Same claim (CLM-8842). One guard deleted - action de-duplication -")
    print("and nothing else about the agent changed. That is the required")
    print('shape: "the working agent, minus X." Putting X back recovers the')
    print("behaviour, which is what makes this a diagnosis, not a story.")
    print()

    dist = failure1_loop.turn_distribution()
    print("First, the real 50-case evaluation set, so the cap has context:")
    print("  median turns: {median}   min: {min}   max: {max}   "
          "hit the {cap}-turn cap: {hit_cap}/{n}".format(
              cap=config.MAX_STEPS, **dist))
    print("  -> nowhere near the cap. Nothing legitimate looks like what")
    print("     you're about to see.")
    print()

    print("-" * 72)
    print("BEFORE: max_repeats=999 (de-duplication effectively deleted)")
    print("-" * 72)
    broken = failure1_loop.run_once(max_repeats=999)
    print("  decision: {}   trigger: {}".format(
        broken.decision, broken.detail.get("trigger")))
    print("  turns: {}   tool_calls: {}   input tokens: ~{}".format(
        broken.steps, broken.tool_calls, broken.input_tokens_est))
    print("  No exception was raised. It just re-asked the same question")
    print("  {} times and burned the whole step cap before stopping."
          .format(broken.tool_calls))
    print()

    print("-" * 72)
    print("AFTER: max_repeats={} (the guard restored)".format(config.MAX_REPEATS))
    print("-" * 72)
    fixed = failure1_loop.run_once(max_repeats=config.MAX_REPEATS)
    print("  decision: {}   trigger: {}".format(
        fixed.decision, fixed.detail.get("trigger")))
    print("  turns: {}   tool_calls: {}   input tokens: ~{}".format(
        fixed.steps, fixed.tool_calls, fixed.input_tokens_est))
    print()

    ratio = broken.steps / fixed.steps
    tok_ratio = broken.input_tokens_est / fixed.input_tokens_est
    print("=" * 72)
    print("{:.1f}x the turns, {:.1f}x the input tokens, for the SAME failure "
          "- caught in {} turns instead of {}.".format(
              ratio, tok_ratio, fixed.steps, broken.steps))
    print("De-duplication catches this cheaply and specifically. The step "
          "cap would")
    print("eventually have caught it too, but only after paying for all "
          "{} turns.".format(config.MAX_STEPS))
    print("=" * 72)


if __name__ == "__main__":
    main()
