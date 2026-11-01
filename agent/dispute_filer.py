"""File generated dispute packets through the authenticated portal API."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

import requests

from .dispute_builder import DisputePacket, PacketBatch
from .portal_client import PortalClient

TRANSIENT_STATUSES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class FilingSummary:
    total_eligible: int
    successfully_filed: int = 0
    failed: int = 0
    skipped_flagged: int = 0
    skipped_already_filed: int = 0
    errors: list[str] = field(default_factory=list)

    def print(self) -> None:
        print("\nDeductionDesk dispute filing summary")
        print("=" * 39)
        print(f"Total eligible:          {self.total_eligible}")
        print(f"Successfully filed:      {self.successfully_filed}")
        print(f"Failed:                  {self.failed}")
        print(f"Skipped (human review):  {self.skipped_flagged}")
        print(f"Skipped (already filed): {self.skipped_already_filed}")
        print(f"Errors:                  {len(self.errors)}")
        for error in self.errors:
            print(f"  - {error}")


class DisputeFiler:
    def __init__(self, portal: PortalClient | None = None, max_attempts: int = 3) -> None:
        self.portal = portal or PortalClient()
        self._owns_portal = portal is None
        self.max_attempts = max_attempts

    def _file_one(self, packet: DisputePacket) -> tuple[bool, str | None]:
        payload = {
            "deduction_id": packet.deduction_id,
            "packet_markdown": packet.markdown,
            "claimed_amount": str(packet.claimed_amount),
            "agent_confidence": packet.agent_confidence,
        }
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.portal.post_json("/api/disputes", payload)
                if response.ok:
                    return True, None
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code not in TRANSIENT_STATUSES:
                    break
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
        return False, last_error

    def file_batch(self, batch: PacketBatch) -> FilingSummary:
        summary = FilingSummary(
            total_eligible=len(batch.packets),
            skipped_flagged=batch.skipped_flagged,
            skipped_already_filed=batch.skipped_already_filed,
        )
        total = len(batch.packets)
        for index, packet in enumerate(batch.packets, 1):
            success, error = self._file_one(packet)
            if success:
                summary.successfully_filed += 1
                print(f"Filed {index}/{total} deduction={packet.deduction_id}")
            else:
                summary.failed += 1
                message = f"deduction {packet.deduction_id}: {error or 'unknown error'}"
                summary.errors.append(message)
                print(f"Failed {index}/{total} {message}")
        return summary

    def close(self) -> None:
        if self._owns_portal:
            self.portal.close()
