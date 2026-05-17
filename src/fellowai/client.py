"""Single point of contact with Fellow's REST API."""

from __future__ import annotations

import json
import time
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


ALLOWED_RECORDING_FILTERS: frozenset[str] = frozenset({
    "event_guid", "created_at_start", "created_at_end",
    "updated_at_start", "updated_at_end", "channel_id", "title",
})
ALLOWED_RECORDING_INCLUDES: frozenset[str] = frozenset({
    "transcript", "ai_notes", "media_url",
})
ALLOWED_NOTE_FILTERS: frozenset[str] = frozenset({"created_at_start", "created_at_end"})
ALLOWED_NOTE_INCLUDES: frozenset[str] = frozenset({"content_markdown", "event_attendees"})
ALLOWED_ACTION_ITEM_FILTERS: frozenset[str] = frozenset({
    "scope", "completed", "archived", "ai_detected", "ai_suggestion_accepted_by_user",
})
ALLOWED_ACTION_ITEM_ORDER_BY: frozenset[str] = frozenset({
    "created_at_desc", "created_at_asc", "due_date",
})


def _validate_keys(value: dict | None, allowed: frozenset[str], kind: str) -> None:
    if not value:
        return
    bad = set(value.keys()) - allowed
    if bad:
        raise ValueError(f"Unknown {kind}: {sorted(bad)}. Allowed: {sorted(allowed)}.")


class FellowClient:
    def __init__(self, *, subdomain: str, api_key: str, timeout: float = 30.0) -> None:
        self._subdomain = subdomain
        self._base = f"https://{subdomain}.fellow.app/api/v1"
        self._http = httpx.Client(
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    _MAX_RETRIES = 3

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        attempt = 0
        while True:
            resp = self._http.request(method, url, json=json_body)
            if resp.status_code == 429 and attempt < self._MAX_RETRIES:
                wait = float(resp.headers.get("Retry-After", 2**attempt))
                time.sleep(wait)
                attempt += 1
                continue
            if 500 <= resp.status_code < 600 and attempt < self._MAX_RETRIES:
                time.sleep(2**attempt)
                attempt += 1
                continue
            break

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
        return self._request("GET", f"/recording/{recording_id}")["recording"]

    def list_recordings(
        self,
        *,
        filters: dict | None = None,
        include: dict | None = None,
        media_url: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        _validate_keys(filters, ALLOWED_RECORDING_FILTERS, "filter")
        _validate_keys(include, ALLOWED_RECORDING_INCLUDES, "include")
        return self._paginate(
            "/recordings",
            response_key="recordings",
            filters=filters,
            include=include,
            extra_body={"media_url": media_url} if media_url else None,
            order_by=order_by,
            limit=limit,
            page_size=page_size,
        )

    def _paginate(
        self,
        path: str,
        *,
        response_key: str,
        filters: dict | None,
        include: dict | None,
        extra_body: dict | None = None,
        order_by: str | None = None,
        limit: int | None,
        page_size: int,
    ) -> Iterator[dict]:
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")

        cursor: str | None = None
        yielded = 0
        while True:
            body: dict = {"pagination": {"cursor": cursor, "page_size": page_size}}
            if filters:
                body["filters"] = filters
            if include:
                body["include"] = include
            if order_by:
                body["order_by"] = order_by
            if extra_body:
                body.update(extra_body)

            data = self._request("POST", path, json_body=body)
            page = data[response_key]
            for item in page["data"]:
                if limit is not None and yielded >= limit:
                    return
                yield item
                yielded += 1
            cursor = page["page_info"]["cursor"]
            if cursor is None:
                return

    def list_notes(
        self,
        *,
        filters: dict | None = None,
        include: dict | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        _validate_keys(filters, ALLOWED_NOTE_FILTERS, "filter")
        _validate_keys(include, ALLOWED_NOTE_INCLUDES, "include")
        return self._paginate(
            "/notes",
            response_key="notes",
            filters=filters,
            include=include,
            limit=limit,
            page_size=page_size,
        )

    def get_note(self, note_id: str) -> dict:
        return self._request("GET", f"/note/{note_id}")["note"]

    def list_action_items(
        self,
        *,
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        _validate_keys(filters, ALLOWED_ACTION_ITEM_FILTERS, "filter")
        if order_by is not None and order_by not in ALLOWED_ACTION_ITEM_ORDER_BY:
            raise ValueError(
                f"Unknown order_by: {order_by!r}. Allowed: {sorted(ALLOWED_ACTION_ITEM_ORDER_BY)}."
            )
        return self._paginate(
            "/action_items",
            response_key="action_items",
            filters=filters,
            include=None,
            order_by=order_by,
            limit=limit,
            page_size=page_size,
        )

    def get_action_item(self, action_item_id: str) -> dict:
        return self._request("GET", f"/action_item/{action_item_id}")["action_item"]

    def set_action_item_completed(self, action_item_id: str, completed: bool) -> dict:
        return self._request(
            "POST",
            f"/action_item/{action_item_id}/complete",
            json_body={"completed": completed},
        )["action_item"]

    def archive_action_item(self, action_item_id: str) -> dict:
        return self._request("POST", f"/action_item/{action_item_id}/archive", json_body={})["action_item"]
