from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
import json

class DashboardServer:
    def __init__(self, event_bus):
        self.app = FastAPI()
        self.event_bus = event_bus
        self.queue: asyncio.Queue = asyncio.Queue()

        @self.app.get("/")
        async def index():
            return HTMLResponse(self._html())

        @self.app.get("/events")
        async def events():
            async def event_stream():
                while True:
                    event = await self.queue.get()
                    yield f"data: {json.dumps(event)}\\n\\n"
            return StreamingResponse(event_stream(), media_type="text/event-stream")

        original_emit = event_bus.emit

        def patched_emit(event):
            original_emit(event)
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self.queue.put(event.__dict__))
            except RuntimeError:
                # no running loop; ignore live streaming
                pass

        event_bus.emit = patched_emit

    def _html(self):
        return """
        <html>
        <body>
            <h1>Agent Dashboard</h1>
            <pre id="log"></pre>
            <script>
                const log = document.getElementById("log");
                const evtSource = new EventSource("/events");
                evtSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    log.textContent += JSON.stringify(data, null, 2) + "\\n";
                };
            </script>
        </body>
        </html>
        """

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)
