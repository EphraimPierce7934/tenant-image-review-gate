import base64
import json

import httpx
import pytest
from moderation_service.infrai_images import InfraiImages


@pytest.mark.asyncio
async def test_upload_sends_auth_fields_and_idempotency_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Idempotency-Key"] == "submission-123"
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == {
            "file": base64.b64encode(b"image-bytes").decode("ascii"),
            "filename": "cover.jpg",
            "idempotency_key": "submission-123",
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {"id": "img_123"},
                "error": None,
                "metadata": {},
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = InfraiImages("test-key", client=http_client)
        uploaded = await client.upload(
            content=b"image-bytes",
            filename="cover.jpg",
            idempotency_key="submission-123",
        )

    assert uploaded == {"id": "img_123"}
