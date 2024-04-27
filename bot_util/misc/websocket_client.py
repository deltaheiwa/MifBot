from typing import Any, Dict
import websockets
import websockets.exceptions
import asyncio
import json
import logging

from icecream import ic


logger = logging.getLogger(__name__)


class WebSocketClient:
    def __init__(self):
        self.uri: str = "ws://localhost:8080"
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.loop = asyncio.get_event_loop()

    async def heartbeat(self):
        while True:
            try:
                if self.ws:
                    await self.ws.ping()
                    await asyncio.sleep(10)
                else:

                    await asyncio.sleep(1)
            except websockets.exceptions.ConnectionClosed:
                break

    async def connect(self):
        try:
            self.ws = await websockets.connect(self.uri)
        except Exception as e:
            ic(f"Failed to connect to WebSocket: {e}")

    async def send(self, type_of_data: str, data: Any):
        message = json.dumps({"type": type_of_data, "data": data})
        await self.ws.send(message)

    async def receive(self, raw: bool = False):
        if self.ws is None:
            raise ConnectionError("No WebSocket connection")

        message = await self.ws.recv()
        if raw:
            return message

        await self.handle_message(message)

    @staticmethod
    def process_json(message: str) -> tuple[str | None, Any | None]:
        try:
            decoded: Dict[str, Any] = json.loads(message)
            message_type: str = decoded.get("type", "")
            data: Any = decoded.get("data", "")
        except json.JSONDecodeError:
            ic("Invalid message format received")
            return None, None

        return message_type, data

    async def handle_message(self, message: str):
        message_type, data = self.process_json(message)
        if not message_type:
            raise AttributeError("Type is missing")

        match message_type:
            case _:
                pass

        return

    async def close(self):
        if self.ws:
            await self.ws.close()

    def run(self):
        self.loop.run_until_complete(
            asyncio.gather(
                self.connect(),
                self.heartbeat
                )
            )

    def stop(self):
        self.loop.run_until_complete(self.close())
