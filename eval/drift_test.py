"""Exercise PortalClient against deterministic API-drift mutations."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "eval" / "reports"
SCENARIOS_DIR = ROOT / "eval" / "drift_scenarios"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.portal_client import (  # noqa: E402
    PortalClient,
    PortalClientError,
    SchemaChangeDetected,
)


BASE_ROW = {
    "id": 9001,
    "retailer": "Drift Test Retailer",
    "type": "shortage",
    "claimed_amount": "42.50",
    "status": "pending",
    "retailer_notes": "Reason: SHORTAGE. qty 5.",
    "invoice_id": 7001,
}

SCENARIOS = {
    "renamed_field": {
        "description": "claimed_amount renamed to deduction_amt",
        "expected": "schema_change_detected",
    },
    "pagination_meta": {
        "description": "pagination object renamed to meta",
        "expected": "graceful_error",
    },
    "extra_auth_step": {
        "description": "deductions endpoint returns 403 and requires retry-token header",
        "expected": "graceful_error",
    },
}


def _response(status: int, payload: Any) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.url = "http://mutated-portal.local/api/deductions"
    response.headers["Content-Type"] = "application/json"
    response._content = json.dumps(payload).encode("utf-8")  # noqa: SLF001 - controlled test double
    return response


class MutatedSession:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def post(self, *_args: object, **_kwargs: object) -> requests.Response:
        return _response(200, {"token": "test-jwt"})

    def get(self, *_args: object, **_kwargs: object) -> requests.Response:
        if self.scenario == "renamed_field":
            row = {**BASE_ROW, "deduction_amt": BASE_ROW["claimed_amount"]}
            row.pop("claimed_amount")
            return _response(200, {"data": [row], "pagination": {"total_pages": 1}})
        if self.scenario == "pagination_meta":
            return _response(200, {"data": [BASE_ROW], "meta": {"page": 1, "total_pages": 1}})
        return _response(403, {"error": "retry-token header required", "required_header": "retry-token"})

    def close(self) -> None:
        return None


def _classify_outcome(scenario: str) -> dict[str, object]:
    client = PortalClient()
    client.session.close()
    client.session = MutatedSession(scenario)  # type: ignore[assignment]
    try:
        rows = client.fetch_deductions(limit=1)
        outcome = "silent_misparse" if rows else "silent_empty"
        message = f"Client returned {len(rows)} row(s) without reporting schema drift."
    except SchemaChangeDetected as exc:
        outcome = "schema_change_detected"
        message = (
            f"{type(exc).__name__}: {exc}; "
            f"missing_fields={exc.missing_fields}; present_keys={exc.present_keys}"
        )
    except PortalClientError as exc:
        outcome = "graceful_error"
        message = str(exc)
    except Exception as exc:  # Deliberately distinguish an unwrapped crash from graceful detection.
        outcome = "crash"
        message = f"{type(exc).__name__}: {exc}"
    finally:
        client.close()
    passed = outcome == str(SCENARIOS[scenario]["expected"])
    return {
        "scenario": scenario,
        "description": SCENARIOS[scenario]["description"],
        "expected": SCENARIOS[scenario]["expected"],
        "outcome": outcome,
        "passed": passed,
        "message": message,
    }


def generate_report(
    *, print_report: bool = True, scenarios: list[str] | None = None
) -> dict[str, object]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    for name, config in SCENARIOS.items():
        (SCENARIOS_DIR / f"{name}.json").write_text(
            json.dumps({"name": name, **config}, indent=2) + "\n", encoding="utf-8"
        )

    selected = scenarios or list(SCENARIOS)
    unknown = sorted(set(selected) - set(SCENARIOS))
    if unknown:
        raise ValueError(f"Unknown drift scenario(s): {', '.join(unknown)}")
    results = [_classify_outcome(name) for name in selected]
    report = {
        "definition_of_pass": (
            "Renamed fields must raise SchemaChangeDetected with missing and present keys; "
            "other drift must raise a clear PortalClientError. No scenario may return corrupted deductions."
        ),
        "passed": sum(bool(result["passed"]) for result in results),
        "total": len(results),
        "results": results,
    }
    report_path = REPORTS_DIR / "drift_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if print_report:
        print("# Portal Drift Resilience\n")
        print(f"Pass means: {report['definition_of_pass']}\n")
        print("| Scenario | Result | Observed behavior | Detail |")
        print("|---|---|---|---|")
        for result in results:
            status = "PASS" if result["passed"] else "FAIL"
            safe_message = str(result["message"]).replace("|", "\\|").replace("\n", " ")
            print(f"| {result['scenario']} | {status} | {result['outcome']} | {safe_message} |")
        print(f"\nPassed {report['passed']}/{report['total']} scenarios.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run portal API drift scenarios")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), action="append")
    arguments = parser.parse_args()
    generate_report(scenarios=arguments.scenario)
