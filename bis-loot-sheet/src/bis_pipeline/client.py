"""Rate-limit-aware GraphQL client for the Warcraft Logs classic v2 API.

Every request piggybacks `rateLimitData` so the budget ledger is WCL's own,
not a local estimate. When the remaining hourly budget drops below the safety
margin, the client sleeps until the fixed hourly window resets and resumes.
"""

import json
import logging
import time

import httpx

from .config import (
    CLASSIC_API_URL,
    OAUTH_TOKEN_URL,
    POINTS_SAFETY_MARGIN,
    TOKEN_CACHE,
    load_env,
)

log = logging.getLogger(__name__)

RATE_LIMIT_FRAGMENT = "rateLimitData { limitPerHour pointsSpentThisHour pointsResetIn }"


class WCLClient:
    def __init__(self) -> None:
        self._http = httpx.Client(timeout=60.0)
        self._token = self._obtain_token()
        self.last_rate_limit: dict | None = None
        self._last_status_log = 0.0

    def _obtain_token(self) -> str:
        if TOKEN_CACHE.exists():
            cached = json.loads(TOKEN_CACHE.read_text())
            if cached["expires_at"] > time.time() + 3600:
                return cached["access_token"]
        env = load_env()
        resp = self._http.post(
            OAUTH_TOKEN_URL,
            auth=(env["WCL_CLIENT_ID"], env["WCL_CLIENT_SECRET"]),
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        payload = resp.json()
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(
            json.dumps(
                {
                    "access_token": payload["access_token"],
                    "expires_at": time.time() + payload["expires_in"],
                }
            )
        )
        return payload["access_token"]

    def query(self, query: str, variables: dict | None = None) -> dict:
        """Run a GraphQL query, returning the `data` object.

        Retries transient failures, honors the hourly points budget, and
        stores the latest rateLimitData on `self.last_rate_limit`.
        """
        body = {"query": f"{{ {query} {RATE_LIMIT_FRAGMENT} }}"}
        if variables:
            body["variables"] = variables

        backoff = 5.0
        for _attempt in range(8):
            try:
                resp = self._http.post(
                    CLASSIC_API_URL,
                    json=body,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
            except httpx.HTTPError as exc:
                log.warning("transport error (%s), retrying in %.0fs", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue

            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 60))
                log.warning("HTTP 429, sleeping %.0fs", wait)
                time.sleep(wait + 1)
                continue
            if resp.status_code >= 500:
                log.warning("HTTP %d, retrying in %.0fs", resp.status_code, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            resp.raise_for_status()

            payload = resp.json()
            if "errors" in payload and not payload.get("data"):
                raise RuntimeError(f"GraphQL error: {payload['errors']}")

            data = payload["data"]
            self.last_rate_limit = data.pop("rateLimitData", None)
            self._respect_budget()
            return data

        raise RuntimeError("giving up after repeated attempts")

    def _respect_budget(self) -> None:
        rl = self.last_rate_limit
        if not rl:
            return
        remaining = rl["limitPerHour"] - rl["pointsSpentThisHour"]
        now = time.monotonic()
        if now - self._last_status_log >= 120:
            self._last_status_log = now
            log.info(
                "rate limit: %.0f points left (~%d queries) | window resets in %dm%02ds",
                remaining,
                int(remaining / 1.3),  # ~1.3 points per rankings page, observed
                rl["pointsResetIn"] // 60,
                rl["pointsResetIn"] % 60,
            )
        if remaining < POINTS_SAFETY_MARGIN:
            wait = rl["pointsResetIn"] + 5
            log.info(
                "points budget nearly exhausted (%.1f left), sleeping %ds until reset",
                remaining,
                wait,
            )
            time.sleep(wait)

    def points_status(self) -> dict:
        self.query("worldData { expansions { id } }")
        return self.last_rate_limit or {}
