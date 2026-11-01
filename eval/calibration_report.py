"""Evaluate whether reported confidence tracks empirical correctness."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "eval" / "reports"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.accuracy_report import load_decisions  # noqa: E402


BUCKETS = [
    (0.0, 0.5),
    (0.5, 0.6),
    (0.6, 0.7),
    (0.7, 0.8),
    (0.8, 0.9),
    (0.9, 1.0),
]


def _in_bucket(confidence: float, low: float, high: float) -> bool:
    return low <= confidence <= high if high == 1.0 else low <= confidence < high


def generate_report(*, print_report: bool = True) -> dict[str, object]:
    rows = load_decisions()
    bucket_results: list[dict[str, object]] = []
    for low, high in BUCKETS:
        selected = [row for row in rows if _in_bucket(float(row["confidence"]), low, high)]
        if not selected:
            continue
        average_confidence = sum(float(row["confidence"]) for row in selected) / len(selected)
        accuracy = sum(bool(row["final_is_valid"]) == bool(row["truth_is_valid"]) for row in selected) / len(selected)
        bucket_results.append(
            {
                "bucket": f"{low:.1f}-{high:.1f}",
                "count": len(selected),
                "average_confidence": average_confidence,
                "actual_accuracy": accuracy,
                "gap": average_confidence - accuracy,
            }
        )

    overall_confidence = sum(float(row["confidence"]) for row in rows) / len(rows)
    overall_accuracy = sum(bool(row["final_is_valid"]) == bool(row["truth_is_valid"]) for row in rows) / len(rows)
    gap = overall_confidence - overall_accuracy
    tolerance = 0.01
    verdict = "well-calibrated" if abs(gap) <= tolerance else ("over-confident" if gap > 0 else "under-confident")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(7.2, 5.2))
    axis.plot([0, 1], [0, 1], linestyle="--", color="#9aa6a0", label="Perfect calibration")
    axis.plot(
        [float(item["average_confidence"]) for item in bucket_results],
        [float(item["actual_accuracy"]) for item in bucket_results],
        marker="o",
        linewidth=2,
        color="#176b4d",
        label="DeductionDesk",
    )
    for item in bucket_results:
        axis.annotate(
            f"n={item['count']}",
            (float(item["average_confidence"]), float(item["actual_accuracy"])),
            xytext=(6, -12),
            textcoords="offset points",
            fontsize=8,
        )
    axis.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean reported confidence", ylabel="Actual accuracy", title="DeductionDesk confidence calibration")
    axis.grid(alpha=0.18)
    axis.legend(loc="lower right")
    figure.tight_layout()
    chart_path = REPORTS_DIR / "calibration_chart.png"
    figure.savefig(chart_path, dpi=180)
    plt.close(figure)

    result = {
        "count": len(rows),
        "overall_confidence": overall_confidence,
        "overall_accuracy": overall_accuracy,
        "calibration_gap": gap,
        "verdict": verdict,
        "buckets": bucket_results,
        "chart_path": str(chart_path),
    }
    (REPORTS_DIR / "calibration_report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if print_report:
        print("# DeductionDesk Calibration Report\n")
        print("| Confidence bucket | N | Mean confidence | Actual accuracy | Gap |")
        print("|---|---:|---:|---:|---:|")
        for item in bucket_results:
            print(
                f"| {item['bucket']} | {item['count']} | {float(item['average_confidence']):.2%} | "
                f"{float(item['actual_accuracy']):.2%} | {float(item['gap']):+.2%} |"
            )
        print(
            f"\nOverall: confidence {overall_confidence:.2%}, accuracy {overall_accuracy:.2%}; "
            f"the system is **{verdict}** by {abs(gap):.2%}."
        )
        print(f"Chart: {chart_path}")
    return result


if __name__ == "__main__":
    generate_report()
