from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeo_audit.utils.http import HttpClient
from aeo_audit.utils.validators import (
    validate_agent_manifest,
    validate_did_document,
    validate_json_schema,
    validate_mcp_manifest,
    validate_openapi_spec,
)


def test_validators() -> None:
    assert validate_json_schema({}, {}) == (True, [])
    assert validate_openapi_spec({}) == (True, [])
    assert validate_did_document({}) == (True, [])
    assert validate_mcp_manifest({}) == (True, [])

    # test agent manifest
    valid_manifest = {
        "name": "test",
        "version": "1.0.0",
        "capabilities": {},
        "auth": {},
        "pricing_url": "http://example.com",
    }
    assert validate_agent_manifest(valid_manifest) == (True, [])

    invalid_manifest = {"name": "test"}
    is_valid, errors = validate_agent_manifest(invalid_manifest)
    assert not is_valid
    assert len(errors) == 4


@pytest.mark.asyncio
async def test_http_client() -> None:
    # Test HttpClient error when not in context manager
    client = HttpClient()
    with pytest.raises(RuntimeError):
        await client.get("http://example.com")
    with pytest.raises(RuntimeError):
        await client.post("http://example.com")

    # Mock httpx.AsyncClient
    mock_async_client = AsyncMock()
    mock_response = MagicMock()
    mock_async_client.get.return_value = mock_response
    mock_async_client.post.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_async_client):
        async with HttpClient() as client:
            res = await client.get("http://example.com")
            assert res == mock_response
            res_post = await client.post("http://example.com")
            assert res_post == mock_response
