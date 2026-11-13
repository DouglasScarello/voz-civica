"""
voz_civica/ui/server.py

Servidor local que expõe o estado da conversa (voz_civica.ui.state) numa
página com um orb pulsante, via WebSocket. Roda embutido no mesmo processo
do orquestrador (Estágio 3) — quando o loop asyncio ganhar as camadas de
LLM/TTS (Estágios 4-5), este servidor continua igual, só quem alimenta o
SharedUiState muda.
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from voz_civica.ui.state import SharedUiState

STATIC_DIR = Path(__file__).parent / "static"
BROADCAST_HZ = 25


def build_app(ui_state: SharedUiState) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                snapshot = ui_state.read()
                await websocket.send_json({"state": snapshot.state, "amplitude": snapshot.amplitude})
                await asyncio.sleep(1 / BROADCAST_HZ)
        except WebSocketDisconnect:
            pass

    return app
