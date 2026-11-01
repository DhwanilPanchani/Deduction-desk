"""Run every DeductionDesk Phase 6 evaluation and save a combined summary."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.accuracy_report import generate_report as accuracy_report  # noqa: E402
from eval.calibration_report import generate_report as calibration_report  # noqa: E402
from eval.drift_test import generate_report as drift_report  # noqa: E402


def main() -> int:
    print("=" * 72)
    print("ACCURACY")
    print("=" * 72)
    accuracy = accuracy_report()
    print("\n" + "=" * 72)
    print("CALIBRATION")
    print("=" * 72)
    calibration = calibration_report()
    print("\n" + "=" * 72)
    print("PORTAL DRIFT")
    print("=" * 72)
    drift = drift_report()

    combined = {"accuracy": accuracy, "calibration": calibration, "drift": drift}
    report_path = ROOT / "eval" / "reports" / "combined_summary.json"
    report_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 72)
    print("COMBINED SUMMARY")
    print("=" * 72)
    print(f"Dataset:                 {accuracy['count']} decisions")
    print(f"Overall accuracy:        {float(accuracy['overall_accuracy']):.2%}")
    print(f"Invalid precision:       {float(accuracy['invalid_precision']):.2%}")
    print(f"Invalid recall:          {float(accuracy['invalid_recall']):.2%}")
    print(f"Invalid F1:              {float(accuracy['invalid_f1']):.2%}")
    print(f"Calibration:             {calibration['verdict']} ({float(calibration['calibration_gap']):+.2%})")
    print(f"Drift scenarios passed:  {drift['passed']}/{drift['total']}")
    print(f"Reports:                 {report_path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
