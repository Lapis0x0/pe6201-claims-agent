"""Run the zero-cost repository checks and validate committed evidence."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args):
    print("\n$", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def validate_evidence():
    manifest = json.loads((ROOT / "results" / "manifest.json").read_text())
    assert manifest["primary_metric"] == "passing trials / total trials"
    for item in manifest["canonical_live_runs"]:
        rows = json.loads((ROOT / "results" / item["file"]).read_text())
        passed = sum(bool(row["passed"]) for row in rows)
        assert len(rows) == item["trials"], item["file"]
        assert passed == item["passed_trials"], item["file"]
        assert abs(passed / len(rows) - item["pass_rate"]) < 1e-12

    judgement = json.loads(
        (ROOT / "results" / "judgement_checks.json").read_text()
    )
    assert judgement["passed"] == 2 and judgement["total"] == 10
    assert len(judgement["results"]) == 10
    assert sum(row["verdict"] == "PASS" for row in judgement["results"]) == 2
    print("\nCommitted evidence: manifest valid; judgement checks recorded (2/10).")


def main():
    run(sys.executable, "check_my_data.py")
    run(sys.executable, "harness.py")
    run(sys.executable, "guardrail_checklist.py")
    run(sys.executable, "failure1_loop.py")
    run(sys.executable, "failure2_interface.py")
    run(sys.executable, "measure_parallel.py")
    run(sys.executable, "d6_cost_model.py")
    run(sys.executable, "class4_bill_test.py")
    run(sys.executable, "plot_turn_token_growth.py")
    run(sys.executable, "plot_legacy_d5b.py")
    validate_evidence()
    print("\nALL ZERO-COST SUBMISSION CHECKS PASSED")


if __name__ == "__main__":
    main()
