import traceback
from typing import List

from fastapi import WebSocket
from loguru import logger
import asyncio
import websockets
import json
import logging
from typing import Optional, Callable
import signal
import sys
from datetime import datetime

class WebSocketClient:
    def __init__(self, uri: str, reconnect_delay: int = 5):
        self.uri = uri
        self.reconnect_delay = reconnect_delay
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Callbacks
        self.on_message: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    async def connect(self):
        """Kết nối tới WebSocket server"""
        try:
            logger.info(f"Connecting to {self.uri}...")
            
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=10**7,  # 10MB max message size
                compression=None  # Tắt compression để tăng performance
            )
            
            self.reconnect_attempts = 0
            logger.info(f"Connected to {self.uri}")
            
            if self.on_connect:
                await self.on_connect()
                
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self.on_error:
                await self.on_error(e)
            return False

    async def disconnect(self):
        """Ngắt kết nối"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("Disconnected from WebSocket")
            
            if self.on_disconnect:
                await self.on_disconnect()

    async def send_message(self, message: str):
        """Gửi tin nhắn"""
        if self.websocket:
            try:
                await self.websocket.send(message)
                logger.debug(f"Sent: {message}")
                return True
            except Exception as e:
                logger.error(f"Send failed: {e}")
                return False
        else:
            logger.warning("WebSocket not connected, cannot send message")
            return False

    async def send_json(self, data: dict):
        """Gửi JSON data"""
        return await self.send_message(json.dumps(data))

    async def listen(self):
        """Lắng nghe tin nhắn từ server"""
        try:
            while self.running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=30.0
                    )
                    
                    logger.debug(f"Received: {message}")
                    
                    if self.on_message:
                        await self.on_message(message)
                        
                except asyncio.TimeoutError:
                    # Timeout bình thường, tiếp tục loop
                    continue
                    
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"Connection closed: {e.code} - {e.reason}")
                    break
                    
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"Listen error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Listen loop error: {e}")

    async def run_with_reconnect(self):
        """Chạy client với auto reconnect"""
        self.running = True
        
        while self.running:
            try:
                # Thử kết nối
                if await self.connect():
                    # Nếu kết nối thành công, bắt đầu listen
                    await self.listen()
                
                # Nếu đến đây có nghĩa là kết nối bị đứt
                if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
                    self.reconnect_attempts += 1
                    logger.info(f"Reconnecting in {self.reconnect_delay}s... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
                    await asyncio.sleep(self.reconnect_delay)
                elif self.reconnect_attempts >= self.max_reconnect_attempts:
                    logger.error("Max reconnect attempts reached. Stopping.")
                    break
                    
            except Exception as e:
                logger.error(f"Run loop error: {e}")
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)

    async def stop(self):
        """Dừng client"""
        logger.info("Stopping WebSocket client...")
        await self.disconnect()
