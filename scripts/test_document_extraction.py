"""Test script for synthetic document generation and extraction accuracy."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import settings
from agent.document_extractor import DocumentExtractor, ExtractedDeduction
from agent.document_generator import DocumentGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic remittance PDFs and benchmark extraction accuracy"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Number of synthetic remittance PDFs to generate (default: 25)",
    )
    parser.add_argument(
        "--run-llm",
        action="store_true",
        default=False,
        help="Execute LLM extraction path against configured LLM provider (default: False)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(ROOT / "data" / "synthetic_remittances"),
        help="Directory to save generated PDFs",
    )
    return parser.parse_args()


def evaluate_extracted(
    extracted: ExtractedDeduction, gt: dict[str, Any]
) -> dict[str, Any]:
    po_ok = extracted.po_number == gt["po_number"]
    inv_ok = extracted.invoice_number == gt["invoice_number"]
    amt_ok = (
        extracted.claimed_amount is not None
        and float(extracted.claimed_amount) == float(gt["claimed_amount"])
    )
    type_ok = extracted.deduction_type == gt["deduction_type"]
    all_ok = po_ok and inv_ok and amt_ok and type_ok
    return {
        "po_ok": po_ok,
        "inv_ok": inv_ok,
        "amt_ok": amt_ok,
        "type_ok": type_ok,
        "all_ok": all_ok,
        "extracted": extracted,
        "gt": gt,
    }


def print_tier_stats(name: str, items: list[dict[str, Any]]) -> None:
    n = len(items)
    if n == 0:
        print(f"  {name:12s}: N=0")
        return
    exact = sum(1 for x in items if x["all_ok"])
    po = sum(1 for x in items if x["po_ok"])
    inv = sum(1 for x in items if x["inv_ok"])
    amt = sum(1 for x in items if x["amt_ok"])
    dtype = sum(1 for x in items if x["type_ok"])
    print(
        f"  {name:12s} (N={n:2d}): Exact={exact:2d}/{n} ({exact / n:6.1%}) | "
        f"PO={po:2d}/{n} ({po / n:5.1%}) | Inv={inv:2d}/{n} ({inv / n:5.1%}) | "
        f"Amt={amt:2d}/{n} ({amt / n:5.1%}) | Type={dtype:2d}/{n} ({dtype / n:5.1%})"
    )


def main() -> None:
    args = parse_args()

    print("=" * 85)
    print("REMITTANCE DOCUMENT GENERATION & EXTRACTION BENCHMARK")
    print("=" * 85)
    print(f"Target count:       {args.count} synthetic PDFs (Clean + Hard mixed tiers)")
    print(f"Output directory:   {args.output_dir}")
    print(f"LLM Provider:       {settings.llm_provider.upper()} ({settings.groq_model if settings.llm_provider == 'groq' else settings.ollama_model})")
    print(f"LLM Fallback Run:   {'ENABLED (Live API calls)' if args.run_llm else 'DISABLED (Non-LLM only)'}")
    print("=" * 85 + "\n")

    # Step 1: Generate synthetic PDFs across mixed difficulty tiers
    print(f"Generating {args.count} synthetic remittance PDFs (clean tabular + hard narrative)...")
    generator = DocumentGenerator(output_dir=args.output_dir)
    gt_list = generator.generate_batch(count=args.count, split_tiers=True)
    clean_gt = [x for x in gt_list if x.get("difficulty_tier") == "clean"]
    hard_gt = [x for x in gt_list if x.get("difficulty_tier") == "hard"]
    print(f"Generated {len(gt_list)} PDFs: {len(clean_gt)} clean tier, {len(hard_gt)} hard tier.\n")

    extractor = DocumentExtractor()

    # Step 2: Benchmark Non-LLM extraction on both tiers
    print("Phase 1: Evaluating Non-LLM Extraction Path (pdfplumber table/regex alone)...")
    non_llm_evals: list[dict[str, Any]] = []
    for item in gt_list:
        res = extractor.extract_non_llm(item["filepath"])
        ev = evaluate_extracted(res, item)
        ev["tier"] = item.get("difficulty_tier", "clean")
        non_llm_evals.append(ev)

    clean_non_llm = [x for x in non_llm_evals if x["tier"] == "clean"]
    hard_non_llm = [x for x in non_llm_evals if x["tier"] == "hard"]

    print("\nNon-LLM Extraction Accuracy by Tier:")
    print_tier_stats("Clean Tier", clean_non_llm)
    print_tier_stats("Hard Tier", hard_non_llm)
    print_tier_stats("Total Set", non_llm_evals)

    # Step 3: Run LLM-fallback path if requested
    llm_triggered_clean = 0
    llm_triggered_hard = 0
    api_calls_used = 0
    extraction_errors: list[dict[str, Any]] = []
    fallback_evals: list[dict[str, Any]] = []
    hard_llm_evals: list[dict[str, Any]] = []

    if args.run_llm:
        print("\n" + "=" * 85)
        print("Phase 2: Running Extraction Pipeline with LLM Fallback (LLM_PROVIDER=groq)...")
        print("=" * 85)

        for idx, item in enumerate(gt_list, 1):
            tier = item.get("difficulty_tier", "clean")
            res, triggered = extractor.extract(item["filepath"], run_llm=True)

            if triggered:
                if tier == "clean":
                    llm_triggered_clean += 1
                else:
                    llm_triggered_hard += 1

            if res.error:
                extraction_errors.append(
                    {
                        "filename": item["filename"],
                        "tier": tier,
                        "error": res.error,
                    }
                )

            ev = evaluate_extracted(res, item)
            ev["tier"] = tier
            ev["triggered_llm"] = triggered
            fallback_evals.append(ev)

            if tier == "hard" and triggered:
                hard_llm_evals.append(ev)

            print(
                f"  [{idx:02d}/{len(gt_list):02d}] {item['filename']} ({tier:5s}) -> "
                f"Method={res.extraction_method:14s} | LLM Triggered={str(triggered):5s} | "
                f"Exact Match={'YES' if ev['all_ok'] else 'NO'}"
            )

        provider = extractor._get_provider()
        api_calls_used = getattr(provider, "call_count", 0)

        print("\n" + "=" * 85)
        print("PIPELINE PERFORMANCE WITH LLM FALLBACK")
        print("=" * 85)

        print("\nLLM-Fallback Triggering Rate:")
        print(f"  Clean Tier:  {llm_triggered_clean}/{len(clean_gt)} triggered ({llm_triggered_clean / max(len(clean_gt), 1):.1%})")
        print(f"  Hard Tier:   {llm_triggered_hard}/{len(hard_gt)} triggered ({llm_triggered_hard / max(len(hard_gt), 1):.1%})")
        total_triggered = llm_triggered_clean + llm_triggered_hard
        print(f"  Total Calls: {total_triggered}/{len(gt_list)} ({total_triggered / len(gt_list):.1%})")
        print(f"  Total API Calls Used by Provider: {api_calls_used}")

        print("\nAccuracy Breakdown Post-Fallback:")
        clean_fallback = [x for x in fallback_evals if x["tier"] == "clean"]
        hard_fallback = [x for x in fallback_evals if x["tier"] == "hard"]
        print_tier_stats("Clean Tier", clean_fallback)
        print_tier_stats("Hard Tier (LLM Fallback)", hard_fallback)
        print_tier_stats("Overall Blended", fallback_evals)

        if extraction_errors:
            print(f"\nExtraction Errors Encountered ({len(extraction_errors)}):")
            for err in extraction_errors:
                print(f"  - {err['filename']} [{err['tier']}]: {err['error']}")
        else:
            print("\nExtraction Errors: NONE (0 errors)")

    else:
        print("\n[NOTE] LLM-based fallback path was not executed (--run-llm not passed).")
        print("       Ready to test, not yet run.")

    # Step 4: Show Sample Audit (One clean, One hard)
    print("\n" + "=" * 85)
    print("DETAILED EXTRACTION AUDIT SAMPLES")
    print("=" * 85)

    samples_to_show = []
    if clean_gt:
        samples_to_show.append((clean_gt[0], "Clean Tier (Tabular Remittance)"))
    if hard_gt:
        samples_to_show.append((hard_gt[0], "Hard Tier (Narrative Debit Memo)"))

    for item, label in samples_to_show:
        res = extractor.extract_non_llm(item["filepath"])
        print(f"\n--- {label}: {item['filename']} ---")
        preview = (res.raw_text or "").strip().splitlines()[:6]
        for line in preview:
            print(f"  | {line}")
        print("Non-LLM Parsed Fields:")
        print(f"  PO Number:       '{res.po_number}' (GT: '{item['po_number']}')")
        print(f"  Invoice Number:  '{res.invoice_number}' (GT: '{item['invoice_number']}')")
        print(f"  Claimed Amount:  ${res.claimed_amount} (GT: ${Decimal(str(item['claimed_amount'])):.2f})")
        print(f"  Deduction Type:  '{res.deduction_type}' (GT: '{item['deduction_type']}')")
        print(f"  Method Used:     {res.extraction_method} (Confidence: {res.confidence})")

        if args.run_llm:
            llm_res = extractor.extract_with_llm(item["filepath"])
            print("LLM-Fallback Parsed Fields:")
            print(f"  PO Number:       '{llm_res.po_number}'")
            print(f"  Invoice Number:  '{llm_res.invoice_number}'")
            print(f"  Claimed Amount:  ${llm_res.claimed_amount}")
            print(f"  Deduction Type:  '{llm_res.deduction_type}'")
            print(f"  Method Used:     {llm_res.extraction_method} (Confidence: {llm_res.confidence})")

    print("\n" + "=" * 85)


if __name__ == "__main__":
    main()
