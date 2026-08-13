from __future__ import annotations

import json
import math
import mimetypes
import secrets
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .errors import GraphAPIError
from .util import sanitize


def _encode_field(value: Any) -> str:
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


class MetaGraphClient:
    def __init__(
        self,
        token: str,
        *,
        graph_version: str = "v25.0",
        base_url: str = "https://graph.facebook.com",
        timeout: int = 60,
        max_http_attempts: int = 250,
        stop_at_usage_percent: float = 90,
    ) -> None:
        if not token:
            raise GraphAPIError("A non-empty access token is required")
        self._token = token
        self.graph_version = graph_version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_http_attempts = max_http_attempts
        self.stop_at_usage_percent = stop_at_usage_percent
        self.last_usage: dict[str, Any] = {}
        self._request_total = 0
        self._request_methods: dict[str, int] = {}
        self._request_endpoints: dict[str, int] = {}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{self.graph_version}/{path.lstrip('/')}"

    @staticmethod
    def _business_usage_percent(value: Any) -> float:
        candidates: list[float] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"call_count", "total_cputime", "total_time"} and isinstance(
                    child, (int, float)
                ):
                    candidates.append(float(child))
                elif isinstance(child, (dict, list)):
                    candidates.append(MetaGraphClient._business_usage_percent(child))
        elif isinstance(value, list):
            candidates.extend(MetaGraphClient._business_usage_percent(child) for child in value)
        return max(candidates, default=0.0)

    def _usage_percent(self) -> float:
        candidates: list[float] = []
        for header, value in self.last_usage.items():
            if header == "x-ad-account-usage" and isinstance(value, dict):
                for key in ("acc_id_util_pct", "app_id_util_pct"):
                    child = value.get(key)
                    if isinstance(child, (int, float)):
                        candidates.append(float(child))
            elif header == "x-app-usage" and isinstance(value, dict):
                for key in ("call_count", "total_cputime", "total_time"):
                    child = value.get(key)
                    if isinstance(child, (int, float)):
                        candidates.append(float(child))
            elif header == "x-business-use-case-usage":
                candidates.append(self._business_usage_percent(value))
        return max(candidates, default=0.0)

    def _record_request(self, request: Request) -> None:
        if self._request_total >= self.max_http_attempts:
            raise GraphAPIError(
                f"Local request budget exhausted before another Meta call "
                f"({self._request_total}/{self.max_http_attempts}). Resume later from the receipt."
            )
        usage = self._usage_percent()
        if usage >= self.stop_at_usage_percent:
            raise GraphAPIError(
                f"Meta usage reached {usage:.0f}%, at or above the configured "
                f"{self.stop_at_usage_percent:.0f}% stop threshold. Resume after Meta resets the bucket."
            )
        method = request.get_method().upper()
        endpoint = urlparse(request.full_url).path
        self._request_total += 1
        self._request_methods[method] = self._request_methods.get(method, 0) + 1
        self._request_endpoints[endpoint] = self._request_endpoints.get(endpoint, 0) + 1

    def _capture_usage(self, headers: Any) -> None:
        for header in ("x-app-usage", "x-ad-account-usage", "x-business-use-case-usage"):
            raw = headers.get(header) if headers else None
            if not raw:
                continue
            try:
                self.last_usage[header] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                self.last_usage[header] = str(raw)

    def request_stats(self) -> dict[str, Any]:
        account = self.last_usage.get("x-ad-account-usage", {})
        reset_seconds = 0
        tier = None
        if isinstance(account, dict):
            raw_reset = account.get("reset_time_duration", 0)
            if isinstance(raw_reset, (int, float)) and raw_reset > 0:
                reset_seconds = math.ceil(float(raw_reset))
            raw_tier = account.get("ads_api_access_tier")
            tier = str(raw_tier) if raw_tier else None
        return {
            "total_http_attempts": self._request_total,
            "by_method": dict(sorted(self._request_methods.items())),
            "by_endpoint": dict(sorted(self._request_endpoints.items())),
            "max_observed_usage_percent": self._usage_percent(),
            "ad_account_reset_seconds": reset_seconds,
            "ads_api_access_tier": tier,
            "headers": sanitize(self.last_usage),
        }

    def _request(self, request: Request) -> dict[str, Any]:
        self._record_request(request)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("Accept", "application/json")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                self._capture_usage(response.headers)
        except HTTPError as exc:
            self._capture_usage(exc.headers)
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"http_status": exc.code, "message": raw[:500]}
            error = payload.get("error", payload) if isinstance(payload, dict) else {}
            message = str(error.get("message") or f"HTTP {exc.code}")
            user_detail = ": ".join(
                str(value)
                for value in (error.get("error_user_title"), error.get("error_user_msg"))
                if value
            )
            if user_detail:
                message = f"{message} — {user_detail}"
            graph_error = GraphAPIError(
                f"Meta API error: {message}",
                error_code=error.get("code", exc.code),
                error_subcode=error.get("error_subcode"),
                is_transient=bool(error.get("is_transient", False)),
                fbtrace_id=error.get("fbtrace_id"),
            )
            if graph_error.is_hard_ad_account_throttle:
                raise GraphAPIError(
                    "Meta stopped this run because the ad-account request bucket is exhausted "
                    "(code 17, subcode 2446079). No retry was attempted; resume after reset.",
                    error_code=graph_error.error_code,
                    error_subcode=graph_error.error_subcode,
                    is_transient=graph_error.is_transient,
                    fbtrace_id=graph_error.fbtrace_id,
                ) from exc
            raise graph_error from exc
        except URLError as exc:
            raise GraphAPIError(f"Meta API connection failed: {exc.reason}") from exc
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise GraphAPIError("Meta API returned non-JSON data") from exc
        if not isinstance(payload, dict):
            raise GraphAPIError("Meta API returned an unexpected response shape")
        if payload.get("error"):
            raise GraphAPIError(f"Meta API error: {sanitize(payload['error'])}")
        return payload

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        encoded = urlencode({key: _encode_field(value) for key, value in (params or {}).items()})
        url = self._url(path) + (f"?{encoded}" if encoded else "")
        return self._request(Request(url, method="GET"))

    def get_all(
        self, path: str, *, params: dict[str, Any] | None = None, max_pages: int = 20
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        payload = self.get(path, params=params)
        for _ in range(max_pages):
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise GraphAPIError("Paginated Meta response did not contain a data list")
            rows.extend(item for item in data if isinstance(item, dict))
            next_url = payload.get("paging", {}).get("next")
            if not next_url:
                return rows
            request = Request(str(next_url), method="GET")
            payload = self._request(request)
        raise GraphAPIError(f"Pagination exceeded the safety cap of {max_pages} pages")

    def post(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        encoded = urlencode({key: _encode_field(value) for key, value in data.items()}).encode("utf-8")
        request = Request(self._url(path), data=encoded, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        return self._request(request)

    def post_file(
        self,
        path: str,
        *,
        file_field: str,
        file_path: str | Path,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(file_path).expanduser().resolve()
        boundary = f"----meta-ads-{secrets.token_hex(16)}"
        chunks: list[bytes] = []
        for key, value in (fields or {}).items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                    _encode_field(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{file_field}"; '
                    f'filename="{source.name}"\r\n'
                ).encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                source.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        request = Request(self._url(path), data=b"".join(chunks), method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        return self._request(request)
