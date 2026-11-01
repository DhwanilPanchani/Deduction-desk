"""Command-line entrypoint for the DeductionDesk classification agent."""

from __future__ import annotations

import argparse
import sys

from .pipeline import DeductionPipeline
from .dispute_builder import DisputeBuilder
from .dispute_filer import DisputeFiler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify retailer deductions")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum deductions to process (default: all matching rows)",
    )
    parser.add_argument(
        "--status",
        choices=["pending", "disputed", "accepted"],
        default="pending",
        help="Portal status filter (default: pending)",
    )
    parser.add_argument(
        "--file-disputes",
        action="store_true",
        help="Build and file all confident invalid deduction disputes",
    )
    parser.add_argument(
        "--replay-review-traces",
        action="store_true",
        help="Backfill labeled LLM audit replays for legacy review candidates",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    return args


def main() -> int:
    args = parse_args()
    if args.replay_review_traces:
        pipeline: DeductionPipeline | None = None
        try:
            pipeline = DeductionPipeline()
            stored, errors = pipeline.replay_review_traces()
            print(f"Stored audit replays: {stored}; errors: {len(errors)}")
            for error in errors:
                print(f"  - {error}")
            return 1 if errors else 0
        except Exception as exc:
            print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            if pipeline is not None:
                pipeline.close()

    if args.file_disputes:
        builder: DisputeBuilder | None = None
        filer: DisputeFiler | None = None
        try:
            builder = DisputeBuilder()
            batch = builder.build()
            print(
                f"Built {len(batch.packets)} eligible dispute packets; "
                f"skipping {batch.skipped_flagged} human-review cases and "
                f"{batch.skipped_already_filed} already-filed cases."
            )
            filer = DisputeFiler()
            summary = filer.file_batch(batch)
            summary.print()
            return 1 if summary.failed else 0
        except Exception as exc:
            print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            if builder is not None:
                builder.close()
            if filer is not None:
                filer.close()

    pipeline: DeductionPipeline | None = None
    try:
        pipeline = DeductionPipeline()
        summary = pipeline.run(limit=args.limit, status=args.status)
        summary.print()
        return 1 if summary.errors else 0
    except Exception as exc:
        print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if pipeline is not None:
            pipeline.close()


if __name__ == "__main__":
    raise SystemExit(main())
