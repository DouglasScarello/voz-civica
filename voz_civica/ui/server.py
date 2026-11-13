"""
voz_civica/ui/server.py

Servidor local que expõe o estado da conversa (voz_civica.ui.state) numa
página com um orb pulsante, via WebSocket. Roda embutido no mesmo processo
do orquestrador — quando o loop asyncio ganhar as camadas de LLM/TTS, este
servidor continua igual, só quem alimenta o SharedUiState muda.

O WebSocket é de mão dupla: o servidor empurra estado/amplitude ~25x por
segundo e recebe os cliques dos botões (pausar, silenciar, parar fala).
"""

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from voz_civica.ui.state import SharedUiState

STATIC_DIR = Path(__file__).parent / "static"
BROADCAST_HZ = 25

_ACTIONS = {"toggle_pause", "toggle_mute", "stop_speaking"}


def build_app(ui_state: SharedUiState) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def sender() -> None:
            while True:
                snapshot = ui_state.read()
                await websocket.send_json(
                    {
                        "state": snapshot.state,
                        "amplitude": snapshot.amplitude,
                        "paused": snapshot.paused,
                        "muted": snapshot.muted,
                    }
                )
                await asyncio.sleep(1 / BROADCAST_HZ)

        async def receiver() -> None:
            while True:
                message = await websocket.receive_json()
                action = message.get("action") if isinstance(message, dict) else None
                if action not in _ACTIONS:
                    continue
                if action == "toggle_pause":
                    ui_state.toggle_pause()
                elif action == "toggle_mute":
                    ui_state.toggle_mute()
                elif action == "stop_speaking":
                    ui_state.request_stop()

        receive_task = asyncio.create_task(receiver())
        send_task = asyncio.create_task(sender())
        try:
            # termina quando qualquer lado cair (aba fechada, queda de rede,
            # Ctrl+C) — e engole a exceção do lado que sobrou, em vez de
            # deixar um RuntimeError de "send depois do close" subir pro ASGI
            await asyncio.wait({send_task, receive_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (send_task, receive_task):
                task.cancel()
            await asyncio.gather(send_task, receive_task, return_exceptions=True)

    return app
