"""Tests for the shared aiohttp session."""

import pytest

from locusync.http import close_session, get_session


class TestSharedSession:
    @pytest.mark.asyncio
    async def test_reuses_same_session(self):
        try:
            s1 = await get_session()
            s2 = await get_session()
            assert s1 is s2
            assert not s1.closed
        finally:
            await close_session()

    @pytest.mark.asyncio
    async def test_recreated_after_close(self):
        s1 = await get_session()
        await close_session()
        assert s1.closed
        s2 = await get_session()
        try:
            assert s2 is not s1
            assert not s2.closed
        finally:
            await close_session()
