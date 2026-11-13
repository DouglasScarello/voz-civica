"""
voz_civica/audio/sources/base.py

Contrato base (ABC) para fontes de áudio trocáveis — mesmo Adapter Pattern
usado em civic_framework/adapters/base.py, aqui aplicado a "de onde vem o
áudio" em vez de "de onde vem o dado municipal". Permite trocar microfone
por arquivo (testes, replay) ou uma futura segunda fonte (ex: cabine remota)
sem tocar no resto do pipeline.

Design: a fonte expõe um FLUXO de frames (não uma captura única), porque o
VAD (voz_civica/audio/vad.py) precisa decidir frame a frame quando a fala
começa e termina — inclusive ao rodar sobre um arquivo de teste, pra exercer
exatamente a mesma máquina de estados que a captura ao vivo usa.
"""

from abc import ABC, abstractmethod
from typing import Iterator

import numpy as np


class AudioSource(ABC):
    """
    Interface abstrata para fontes de áudio contínuo.

    Para adicionar uma nova fonte (ex: upload remoto, segunda cabine física):
    crie uma subclasse, implemente `stream_frames()` e `samplerate`.
    """

    @property
    @abstractmethod
    def samplerate(self) -> int:
        """Taxa de amostragem em Hz (ex: 16000)."""

    @abstractmethod
    def stream_frames(self) -> Iterator[np.ndarray]:
        """
        Gera frames de áudio (float32, mono, normalizado [-1, 1]) de tamanho
        fixo (voz_civica.config.settings.frame_size), continuamente.

        Para microfone: bloqueia esperando o próximo frame do hardware.
        Para arquivo: fatia o arquivo inteiro em frames do mesmo tamanho,
        simulando um stream — permite testar o VAD sem microfone.
        """

    def drain_pending(self) -> None:
        """
        Descarta qualquer áudio já capturado e ainda não consumido.

        Usado pelo anti-feedback (Estágio 5): antes/depois de tocar a
        resposta da IA, descarta o que o microfone captou durante a
        reprodução — inclusive a própria voz da IA — pra ela não se
        autoescutar. Sem efeito em fontes sem buffer próprio (ex: arquivo).
        """
