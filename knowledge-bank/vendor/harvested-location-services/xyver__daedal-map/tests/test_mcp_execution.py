import asyncio
import threading
import unittest
from unittest import mock

from mapmover import mcp_execution


class MCPExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_work_does_not_block_event_loop(self):
        gate = threading.Event()
        started = threading.Event()

        def worker():
            started.set()
            gate.wait(timeout=2)
            return "done"

        task = asyncio.create_task(
            mcp_execution.run_mcp_blocking("test_tool", worker, timeout_seconds=2)
        )
        await asyncio.to_thread(started.wait, 1)
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        gate.set()
        self.assertEqual(await task, "done")

    async def test_timeout_keeps_capacity_charged_until_worker_finishes(self):
        gate = threading.Event()
        test_capacity = threading.BoundedSemaphore(1)
        test_executor = mcp_execution.ThreadPoolExecutor(max_workers=1)
        with (
            mock.patch.object(mcp_execution, "_CAPACITY", test_capacity),
            mock.patch.object(mcp_execution, "_EXECUTOR", test_executor),
            mock.patch.object(mcp_execution, "_MAX_WORKERS", 1),
            mock.patch.object(mcp_execution, "_ACTIVE_WORKERS", 0),
        ):
            with self.assertRaises(mcp_execution.MCPExecutionTimeoutError):
                await mcp_execution.run_mcp_blocking(
                    "slow_tool", lambda: gate.wait(timeout=2), timeout_seconds=0.01
                )
            self.assertEqual(
                mcp_execution.execution_status(),
                {"max_workers": 1, "active_workers": 1, "default_timeout_seconds": 120},
            )
            with self.assertRaises(mcp_execution.MCPExecutionCapacityError):
                await mcp_execution.run_mcp_blocking(
                    "second_tool", lambda: None, capacity_wait_seconds=0.01,
                )
            gate.set()
            await asyncio.sleep(0.05)
            self.assertIsNone(await mcp_execution.run_mcp_blocking("third_tool", lambda: None))
            await asyncio.sleep(0.01)
            self.assertEqual(mcp_execution.execution_status()["active_workers"], 0)
        test_executor.shutdown(wait=True)

    async def test_short_capacity_wait_absorbs_small_parallel_burst(self):
        gate = threading.Event()
        started = threading.Event()
        test_capacity = threading.BoundedSemaphore(1)
        test_executor = mcp_execution.ThreadPoolExecutor(max_workers=1)

        def first_worker():
            started.set()
            gate.wait(timeout=1)

        with (
            mock.patch.object(mcp_execution, "_CAPACITY", test_capacity),
            mock.patch.object(mcp_execution, "_EXECUTOR", test_executor),
            mock.patch.object(mcp_execution, "_MAX_WORKERS", 1),
            mock.patch.object(mcp_execution, "_ACTIVE_WORKERS", 0),
        ):
            first = asyncio.create_task(
                mcp_execution.run_mcp_blocking("first_tool", first_worker)
            )
            await asyncio.to_thread(started.wait, 1)
            second = asyncio.create_task(
                mcp_execution.run_mcp_blocking(
                    "second_tool", lambda: "done", capacity_wait_seconds=0.5,
                )
            )
            await asyncio.sleep(0.05)
            gate.set()
            await first
            self.assertEqual(await second, "done")
        test_executor.shutdown(wait=True)

    async def test_timeout_signals_cooperative_cancellation(self):
        cancellation = threading.Event()

        def worker():
            cancellation.wait(timeout=2)

        with self.assertRaises(mcp_execution.MCPExecutionTimeoutError):
            await mcp_execution.run_mcp_blocking(
                "cancellable_tool",
                worker,
                timeout_seconds=0.01,
                cancellation_event=cancellation,
            )
        self.assertTrue(cancellation.wait(timeout=1))


if __name__ == "__main__":
    unittest.main()
