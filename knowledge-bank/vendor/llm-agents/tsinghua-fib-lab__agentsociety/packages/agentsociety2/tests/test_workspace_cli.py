from pathlib import Path

import aiohttp
import pytest

from agentsociety2.society import workspace


class _FakeContent:
    async def iter_chunked(self, chunk_size: int):
        assert chunk_size == 8192
        for chunk in (b"map-", b"data"):
            yield chunk


class _FakeResponse:
    content = _FakeContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, request: dict):
        self._request = request

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def get(self, url: str, *, timeout: aiohttp.ClientTimeout):
        self._request["url"] = url
        self._request["timeout"] = timeout.total
        return _FakeResponse()


@pytest.mark.asyncio
async def test_download_map_file_uses_working_official_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request: dict = {}
    monkeypatch.setattr(
        workspace.aiohttp,
        "ClientSession",
        lambda: _FakeSession(request),
    )

    result = await workspace.download_map_file(tmp_path, timeout=17)
    map_path = tmp_path / ".agentsociety" / "data" / "beijing_map.pb"

    assert result["success"] is True
    assert result["errors"] == []
    assert result["file_path"] == str(map_path.resolve())
    assert request == {"url": workspace.BEIJING_MAP_URL, "timeout": 17}
    assert request["url"] == (
        "https://cloud.tsinghua.edu.cn/f/f5c777485d2748fa8535/?dl=1"
    )
    assert map_path.read_bytes() == b"map-data"
