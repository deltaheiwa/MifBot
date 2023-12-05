import websockets
import asyncio


class WebSocketClient:
    def __init__(self):
        self.uri = "ws://localhost:8080"
        self.ws = None
        self.loop = asyncio.get_event_loop()

    async def connect(self):
        self.ws = await websockets.connect(self.uri)

    async def send(self, data):
        await self.ws.send(data)

    async def receive(self):
        return await self.ws.recv()

    async def close(self):
        await self.ws.close()

    def run(self):
        self.loop.run_until_complete(self.connect())

    def stop(self):
        self.loop.run_until_complete(self.close())
