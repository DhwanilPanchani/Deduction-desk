"""Measure classification performance against Phase 1 hidden ground truth."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "eval" / "reports"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import settings  # noqa: E402


DECISIONS_QUERY = """
SELECT d.id AS deduction_id,
       d.type AS deduction_type,
       ad.method,
       ad.confidence::float AS confidence,
       COALESCE(hr.final_is_valid, ad.is_valid) AS final_is_valid,
       gt.is_valid AS truth_is_valid,
       (hr.id IS NOT NULL) AS human_reviewed
FROM agent_decisions ad
JOIN deductions d ON d.id = ad.deduction_id
JOIN ground_truth gt ON gt.deduction_id = d.id
LEFT JOIN human_reviews hr ON hr.deduction_id = d.id
ORDER BY d.id
"""


@dataclass(frozen=True)
class Metrics:
    count: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    true_invalid: int
    predicted_invalid: int


def load_decisions() -> list[dict[str, object]]:
    """The only agent/ground-truth join in the project lives in this eval harness."""
    with psycopg2.connect(settings.database_url) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(DECISIONS_QUERY)
            return [dict(row) for row in cursor.fetchall()]


def compute_metrics(rows: Iterable[dict[str, object]]) -> Metrics:
    materialized = list(rows)
    tp = sum(not bool(row["final_is_valid"]) and not bool(row["truth_is_valid"]) for row in materialized)
    fp = sum(not bool(row["final_is_valid"]) and bool(row["truth_is_valid"]) for row in materialized)
    fn = sum(bool(row["final_is_valid"]) and not bool(row["truth_is_valid"]) for row in materialized)
    correct = sum(bool(row["final_is_valid"]) == bool(row["truth_is_valid"]) for row in materialized)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    count = len(materialized)
    return Metrics(
        count=count,
        accuracy=correct / count if count else 0.0,
        precision=precision,
        recall=recall,
        f1=f1,
        true_invalid=tp + fn,
        predicted_invalid=tp + fp,
    )


def _group(rows: list[dict[str, object]], key: str) -> dict[str, Metrics]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return {name: compute_metrics(group_rows) for name, group_rows in sorted(grouped.items())}


def _table(groups: dict[str, Metrics], heading: str, label: str) -> list[str]:
    lines = [
        f"## {heading}",
        "",
        f"| {label} | N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | True invalid | Predicted invalid |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metric in groups.items():
        lines.append(
            f"| {name} | {metric.count} | {metric.accuracy:.2%} | "
            f"{metric.precision:.2%} | {metric.recall:.2%} | {metric.f1:.2%} | "
            f"{metric.true_invalid} | {metric.predicted_invalid} |"
        )
    return lines


def generate_report(*, print_report: bool = True) -> dict[str, object]:
    rows = load_decisions()
    overall = compute_metrics(rows)
    by_type = _group(rows, "deduction_type")
    by_method = _group(rows, "method")
    human_reviewed = sum(bool(row["human_reviewed"]) for row in rows)

    lines = [
        "# DeductionDesk Accuracy Report",
        "",
        "`invalid` is the positive class. A human verdict supersedes the agent verdict when present.",
        "",
        "## Overall",
        "",
        "| N | Accuracy | Invalid precision | Invalid recall | Invalid F1 | Human-reviewed |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {overall.count} | {overall.accuracy:.2%} | {overall.precision:.2%} | "
        f"{overall.recall:.2%} | {overall.f1:.2%} | {human_reviewed} |",
        "",
        *_table(by_type, "By deduction type", "Type"),
        "",
        *_table(by_method, "By decision method", "Method"),
    ]
    report = "\n".join(lines) + "\n"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "accuracy_report.md").write_text(report, encoding="utf-8")
    if print_report:
        print(report, end="")
    return {
        "overall_accuracy": overall.accuracy,
        "invalid_precision": overall.precision,
        "invalid_recall": overall.recall,
        "invalid_f1": overall.f1,
        "count": overall.count,
        "human_reviewed": human_reviewed,
        "report_path": str(REPORTS_DIR / "accuracy_report.md"),
    }


if __name__ == "__main__":
    generate_report()
