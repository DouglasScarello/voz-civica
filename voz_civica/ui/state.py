"""
voz_civica/ui/state.py

Estado compartilhado entre o loop de captura (rodando numa thread separada,
por causa do callback síncrono do sounddevice) e o servidor FastAPI/WebSocket
(rodando no loop asyncio principal). Protegido por lock simples — as duas
pontas só leem/escrevem alguns campos escalares, não precisa de nada mais
sofisticado.

Estágio 3: os estados "thinking"/"speaking_ai" ainda são simulados com timer
falso, porque o LLM (Estágio 4) e o TTS (Estágio 5) ainda não existem. Nada
aqui precisa mudar quando eles entrarem — só quem escreve o estado muda.
"""

import threading
from dataclasses import dataclass


@dataclass
class UiSnapshot:
    state: str  # "listening" | "speaking_user" | "thinking" | "speaking_ai"
    amplitude: float  # 0.0–1.0, aproximado


class SharedUiState:
    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = UiSnapshot(state="listening", amplitude=0.0)

    def update(self, state: str | None = None, amplitude: float | None = None) -> None:
        with self._lock:
            if state is not None:
                self._snapshot.state = state
            if amplitude is not None:
                self._snapshot.amplitude = amplitude

    def read(self) -> UiSnapshot:
        with self._lock:
            return UiSnapshot(state=self._snapshot.state, amplitude=self._snapshot.amplitude)
