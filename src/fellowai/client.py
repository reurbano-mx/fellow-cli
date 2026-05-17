"""Single point of contact with Fellow's REST API."""

from __future__ import annotations

import json
from typing import Any, Iterator

import httpx


class FellowError(Exception):
    """Base for all client-mapped Fellow API errors."""


class AuthError(FellowError):
    """401 from API, or non-JSON response (likely wrong subdomain)."""


class NotFoundError(FellowError):
    """404 from API."""


class BadRequestError(FellowError):
    """400 from API."""


class RateLimitError(FellowError):
    """429 from API."""


class ServerError(FellowError):
    """5xx from API."""


class FellowClient:
    def __init__(self, *, subdomain: str, api_key: str, timeout: float = 30.0) -> None:
        self._subdomain = subdomain
        self._base = f"https://{subdomain}.fellow.app/api/v1"
        self._http = httpx.Client(
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        resp = self._http.request(method, url, json=json_body)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise AuthError(
                f"Got non-JSON response from {self._subdomain}.fellow.app — "
                "did you type the subdomain correctly?"
            ) from e

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and resp.text.strip().startswith("<"):
                raise AuthError(
                    f"Got HTML response from {self._subdomain}.fellow.app — "
                    "the subdomain is likely wrong."
                )
            return

        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = {"detail": resp.text or f"HTTP {resp.status_code}"}

        message = self._format_error(body)

        if resp.status_code == 401:
            raise AuthError(message)
        if resp.status_code == 404:
            raise NotFoundError(message)
        if resp.status_code == 429:
            raise RateLimitError(message)
        if resp.status_code >= 500:
            raise ServerError(message)
        if resp.status_code >= 400:
            raise BadRequestError(message)

    @staticmethod
    def _format_error(body: dict) -> str:
        if "detail" in body:
            return str(body["detail"])
        if "errors" in body and isinstance(body["errors"], list):
            parts = [f"{e.get('location', '?')}: {e.get('message', '?')}" for e in body["errors"]]
            return body.get("message", "Validation error") + " — " + "; ".join(parts)
        return str(body)

    # ---- Resource methods (real impls in later tasks) ----

    def get_me(self) -> dict:
        return self._request("GET", "/me")

    def get_recording(self, recording_id: str) -> dict:
        return self._request("GET", f"/recording/{recording_id}")

    def list_recordings(self, *, page_size: int = 20) -> Iterator[dict]:
        # Full pagination + filters in Task 5/7. Stub for now.
        body = {"pagination": {"cursor": None, "page_size": page_size}}
        data = self._request("POST", "/recordings", json_body=body)
        yield from data["recordings"]["data"]
