"""
voz_civica/ui/state.py

Estado compartilhado entre o loop de captura (rodando numa thread separada,
por causa do callback síncrono do sounddevice) e o servidor FastAPI/WebSocket
(rodando no loop asyncio principal). Protegido por lock simples — as duas
pontas só leem/escrevem alguns campos escalares, não precisa de nada mais
sofisticado.

Além do estado visual, guarda três controles vindos dos botões da UI:
- `paused`: pausa/retoma a escuta do microfone;
- `muted`: silencia a voz da IA (a resposta continua sendo gerada);
- stop: pedido de interromper a fala em andamento (consumido pelo playback).
"""

import threading
from dataclasses import dataclass


@dataclass
class UiSnapshot:
    state: str  # "listening" | "thinking" | "speaking_ai" | "paused"
    amplitude: float  # 0.0–1.0 — vem SÓ da voz da IA, nunca do microfone
    paused: bool = False
    muted: bool = False


class SharedUiState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = UiSnapshot(state="listening", amplitude=0.0)
        self._stop = threading.Event()

    def update(self, state: str | None = None, amplitude: float | None = None) -> None:
        with self._lock:
            if state is not None:
                self._snapshot.state = state
            if amplitude is not None:
                self._snapshot.amplitude = amplitude

    def read(self) -> UiSnapshot:
        with self._lock:
            return UiSnapshot(
                state=self._snapshot.state,
                amplitude=self._snapshot.amplitude,
                paused=self._snapshot.paused,
                muted=self._snapshot.muted,
            )

    # --- controles vindos da UI -------------------------------------------

    def toggle_pause(self) -> bool:
        with self._lock:
            self._snapshot.paused = not self._snapshot.paused
            if self._snapshot.paused:
                self._snapshot.state = "paused"
                self._snapshot.amplitude = 0.0
            else:
                self._snapshot.state = "listening"
            return self._snapshot.paused

    def toggle_mute(self) -> bool:
        with self._lock:
            self._snapshot.muted = not self._snapshot.muted
            return self._snapshot.muted

    def request_stop(self) -> None:
        self._stop.set()

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def clear_stop(self) -> None:
        self._stop.clear()
