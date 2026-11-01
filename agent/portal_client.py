"""Authenticated client for the Phase 2 supplier portal API."""

from __future__ import annotations

import logging
from typing import Iterator

import requests
from pydantic import ValidationError

from .config import Settings, settings
from .models import Deduction

logger = logging.getLogger(__name__)


class PortalClientError(RuntimeError):
    pass


class SchemaChangeDetected(Exception):
    """The portal row no longer satisfies the expected deduction contract."""

    def __init__(self, missing_fields: list[str], present_keys: list[str]) -> None:
        self.missing_fields = sorted(set(missing_fields))
        self.present_keys = sorted(set(present_keys))
        missing = ", ".join(self.missing_fields) or "unknown"
        present = ", ".join(self.present_keys) or "none"
        super().__init__(
            f"Portal deduction schema changed: missing expected field(s) [{missing}]; "
            f"response keys present [{present}]"
        )


class PortalClient:
    def __init__(self, config: Settings = settings, timeout: float = 15.0) -> None:
        self.config = config
        self.timeout = timeout
        self.session = requests.Session()
        self.token: str | None = None

    def authenticate(self) -> None:
        try:
            response = self.session.post(
                f"{self.config.portal_url}/api/auth",
                json={
                    "username": self.config.portal_username,
                    "password": self.config.portal_password,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            token = response.json().get("token")
        except (requests.RequestException, ValueError) as exc:
            raise PortalClientError(f"Portal authentication failed: {exc}") from exc

        if not token:
            raise PortalClientError("Portal authentication returned no JWT")
        self.token = token

    def _get(self, path: str, params: dict[str, str | int], retry: bool = True) -> requests.Response:
        if not self.token:
            self.authenticate()
        response = self.session.get(
            f"{self.config.portal_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        if response.status_code == 401 and retry:
            self.authenticate()
            return self._get(path, params, retry=False)
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PortalClientError(f"Portal request failed: {exc}") from exc
        return response

    def iter_deductions(
        self, *, status: str = "pending", limit: int | None = None, page_size: int = 100
    ) -> Iterator[Deduction]:
        page = 1
        yielded = 0
        while limit is None or yielded < limit:
            response = self._get(
                "/api/deductions",
                {"status": status, "page": page, "page_size": page_size},
            )
            try:
                payload = response.json()
                rows = payload["data"]
                pagination = payload["pagination"]
            except (ValueError, KeyError, TypeError) as exc:
                raise PortalClientError("Portal returned an invalid deductions payload") from exc

            for row in rows:
                try:
                    deduction = Deduction.model_validate(row)
                except ValidationError as exc:
                    missing_fields = [
                        str(error["loc"][0])
                        for error in exc.errors()
                        if error.get("type") == "missing" and error.get("loc")
                    ]
                    present_keys = list(row.keys()) if isinstance(row, dict) else []
                    schema_error = SchemaChangeDetected(missing_fields, present_keys)
                    logger.error("%s", schema_error)
                    raise schema_error from exc
                yield deduction
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

            if not rows or page >= int(pagination["total_pages"]):
                return
            page += 1

    def fetch_deductions(
        self, *, status: str = "pending", limit: int | None = None
    ) -> list[Deduction]:
        return list(self.iter_deductions(status=status, limit=limit))

    def post_json(
        self, path: str, payload: dict[str, object], retry_auth: bool = True
    ) -> requests.Response:
        """POST JSON while handling an expired portal token once."""
        if not self.token:
            self.authenticate()
        response = self.session.post(
            f"{self.config.portal_url}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
        )
        if response.status_code == 401 and retry_auth:
            self.authenticate()
            return self.post_json(path, payload, retry_auth=False)
        return response

    def close(self) -> None:
        self.session.close()
