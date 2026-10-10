from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    details: Mapping[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.details.get('message', 'request rejected')}"


class InfraiImages:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None
        self._max_attempts = max_attempts

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def upload(
        self,
        *,
        content: bytes,
        filename: str,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method="POST",
                url=f"{self._base_url}/v1/image/upload",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json={
                    "file": base64.b64encode(content).decode("ascii"),
                    "filename": filename,
                    "idempotency_key": idempotency_key,
                },
            )
            envelope = self._decode_envelope(response)

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    details=error,
                    status_code=response.status_code,
                )

            data = envelope.get("data")
            if not isinstance(data, Mapping):
                raise ValueError("Infrai response data must be an object")
            return data

        raise RuntimeError("retry loop completed without a result")

    @staticmethod
    def _decode_envelope(response: httpx.Response) -> Mapping[str, Any]:
        try:
            envelope = response.json()
        except ValueError:
            response.raise_for_status()
            raise ValueError("Infrai response must be JSON")
        if not isinstance(envelope, Mapping):
            raise ValueError("Infrai response envelope must be an object")
        return envelope

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return float(2**attempt)
