import asyncio
from concurrent import futures
from typing import Dict, Optional

import grpc
from grpc.aio import Server as AioServer
from grpc.aio import ServicerContext as AioServicerContext
from pycityproto.city.sync.v2 import sync_service_pb2 as sync_service
from pycityproto.city.sync.v2 import sync_service_pb2_grpc as sync_grpc

from ...logger import get_logger

__all__ = ["Syncer"]


class Syncer(sync_grpc.SyncServiceServicer):
    def __init__(self, addr: str):
        """
        - **Args**:
            - `addr` (str): The address of the syncer
        """
        self.addr = addr

        self._enter_barrier = asyncio.Barrier(2)
        self._exit_barrier = asyncio.Barrier(2)

        # server
        self.server: Optional[AioServer] = None

        self._name2url: Dict[str, str] = {}

    async def init(self) -> None:
        # Create gRPC server
        self.server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=1))
        sync_grpc.add_SyncServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(self.addr)

        await self.server.start()
        get_logger().info(f"server listening at {self.addr}")

    async def close(self) -> None:
        if self.server:
            await self.server.stop(1)
            await self.server.wait_for_termination()
            self.server = None

    def __del__(self):
        if self.server:
            # The final mechanism for shutting down the server to avoid a situation where it is impossible to exit
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.close())
            loop.close()

    async def SetURL(
        self, request: sync_service.SetURLRequest, context: AioServicerContext
    ) -> sync_service.SetURLResponse:
        """Set the URL of the syncer"""
        self._name2url[request.name] = request.url
        return sync_service.SetURLResponse()

    async def GetURL(
        self, request: sync_service.GetURLRequest, context: AioServicerContext
    ) -> sync_service.GetURLResponse:
        """Get the URL of the syncer"""
        return sync_service.GetURLResponse(url=self._name2url[request.name])

    async def EnterStepSync(
        self, request: sync_service.EnterStepSyncRequest, context: AioServicerContext
    ) -> sync_service.EnterStepSyncResponse:
        get_logger().debug(f"EnterStepSync: {request.name}")
        await self._enter_barrier.wait()
        return sync_service.EnterStepSyncResponse()

    async def ExitStepSync(
        self, request: sync_service.ExitStepSyncRequest, context: AioServicerContext
    ) -> sync_service.ExitStepSyncResponse:
        get_logger().debug(f"ExitStepSync: {request.name}")
        await self._exit_barrier.wait()
        return sync_service.ExitStepSyncResponse()

    async def step(self, close: bool = False) -> bool:
        """
        Directly execute sync step without gRPC call

        - **Args**:
            - `close` (bool): Whether to close this participant

        - **Returns**:
            - bool: Whether this participant needs to be closed
        """
        # Enter sync state
        get_logger().debug("Virtual SyncerClient: Enter sync state")
        await self._enter_barrier.wait()

        # Exit sync state
        get_logger().debug("Virtual SyncerClient: Exit sync state")
        await self._exit_barrier.wait()

        return close
