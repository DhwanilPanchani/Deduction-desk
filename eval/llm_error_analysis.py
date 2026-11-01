"""Diagnose errors among deductions resolved by the LLM path."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sys

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "eval" / "reports" / "llm_error_analysis.md"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import settings  # noqa: E402


QUERY = """
SELECT d.id AS deduction_id,
       d.type AS deduction_type,
       d.retailer_notes,
       ad.method,
       ad.is_valid AS agent_is_valid,
       COALESCE(hr.final_is_valid, ad.is_valid) AS final_is_valid,
       ad.confidence::float AS confidence,
       ad.reasoning,
       gt.is_valid AS truth_is_valid,
       gt.true_reason
FROM agent_decisions ad
JOIN deductions d ON d.id = ad.deduction_id
JOIN ground_truth gt ON gt.deduction_id = d.id
LEFT JOIN human_reviews hr ON hr.deduction_id = d.id
ORDER BY d.id
"""


def note_style(notes: str | None) -> str:
    """Recover the three exact note styles emitted by generator/deductions.py."""
    normalized = (notes or "").strip().lower()
    if normalized.startswith("reason:"):
        return "clean/structured"
    if normalized.startswith("hi team,") and "can you review" in normalized:
        return "email-style"
    if " / " in normalized and normalized.endswith("chk docs"):
        return "sparse-ambiguous"
    return "unclassified"


def _type_rate_table(
    rows: list[dict[str, object]], errors: list[dict[str, object]], key: str, label: str
) -> list[str]:
    totals = Counter(str(row[key]) for row in rows)
    error_counts = Counter(str(row[key]) for row in errors)
    lines = [
        f"## Error rate by {label.lower()}",
        "",
        f"| {label} | LLM decisions | Wrong | Error rate |",
        "|---|---:|---:|---:|",
    ]
    for value in sorted(totals):
        count = totals[value]
        wrong = error_counts[value]
        lines.append(f"| {value} | {count} | {wrong} | {wrong / count:.2%} |")
    return lines


def _style_routing_table(
    all_rows: list[dict[str, object]],
    llm_rows: list[dict[str, object]],
    errors: list[dict[str, object]],
) -> list[str]:
    totals = Counter(str(row["note_style"]) for row in all_rows)
    llm_counts = Counter(str(row["note_style"]) for row in llm_rows)
    error_counts = Counter(str(row["note_style"]) for row in errors)
    lines = [
        "## Note-style routing and LLM error rate",
        "",
        "| Note style | All decisions | Routed to LLM | Wrong LLM verdicts | LLM error rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for style in sorted(totals):
        llm_count = llm_counts[style]
        wrong = error_counts[style]
        rate = f"{wrong / llm_count:.2%}" if llm_count else "n/a"
        lines.append(
            f"| {style} | {totals[style]} | {llm_count} | {wrong} | {rate} |"
        )
    lines.extend(
        [
            "",
            "The generator produced all three styles. In this pipeline run, rules resolved every structured and sparse note, so only email-style notes reached the LLM.",
        ]
    )
    return lines


def generate_report(*, print_report: bool = True) -> dict[str, object]:
    with psycopg2.connect(settings.database_url) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(QUERY)
            rows = [dict(row) for row in cursor.fetchall()]

    for row in rows:
        row["note_style"] = note_style(row.get("retailer_notes"))
    llm_rows = [row for row in rows if row["method"] == "llm"]
    errors = [
        row
        for row in llm_rows
        if bool(row["final_is_valid"]) != bool(row["truth_is_valid"])
    ]

    patterns: Counter[tuple[str, str, str]] = Counter()
    for row in errors:
        direction = (
            "false acceptance (valid)"
            if bool(row["final_is_valid"])
            else "false dispute (invalid)"
        )
        patterns[(str(row["deduction_type"]), str(row["note_style"]), direction)] += 1
    (common_type, common_style, common_direction), common_count = patterns.most_common(1)[0]
    common_share = common_count / len(errors)

    lines = [
        "# LLM Error Analysis",
        "",
        f"LLM decisions: **{len(llm_rows)}**  ",
        f"Wrong final verdicts: **{len(errors)}** ({len(errors) / len(llm_rows):.2%})",
        "",
        *_type_rate_table(llm_rows, errors, "deduction_type", "Deduction type"),
        "",
        *_style_routing_table(rows, llm_rows, errors),
        "",
        "## Most common failure pattern",
        "",
        f"**{common_direction} on {common_type} deductions with {common_style} notes** — "
        f"{common_count} of {len(errors)} wrong verdicts ({common_share:.2%}).",
        "",
        "This label describes the dominant observed type/style/direction combination; it does not infer an unstored model rationale.",
        "",
        "## Concrete wrong-verdict examples",
        "",
    ]

    # Highest-confidence errors are the most operationally important examples.
    examples = sorted(
        errors,
        key=lambda row: (-float(row["confidence"]), int(row["deduction_id"])),
    )[:5]
    for index, row in enumerate(examples, 1):
        agent_verdict = "valid/accept" if bool(row["final_is_valid"]) else "invalid/dispute"
        truth_verdict = "valid" if bool(row["truth_is_valid"]) else "invalid"
        lines.extend(
            [
                f"### {index}. Deduction {row['deduction_id']} — {row['deduction_type']} / {row['note_style']}",
                "",
                f"- Confidence: {float(row['confidence']):.2%}",
                f"- Final verdict: {agent_verdict}; ground truth: {truth_verdict}",
                f"- Retailer notes: {row['retailer_notes']}",
                f"- Agent reasoning: {row['reasoning']}",
                f"- Ground-truth reason: {row['true_reason']}",
                "",
            ]
        )

    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    if print_report:
        print(report, end="")
    return {
        "llm_decisions": len(llm_rows),
        "wrong": len(errors),
        "error_rate": len(errors) / len(llm_rows),
        "most_common_pattern": {
            "deduction_type": common_type,
            "note_style": common_style,
            "direction": common_direction,
            "count": common_count,
        },
        "report_path": str(REPORT_PATH),
    }


if __name__ == "__main__":
    generate_report()
