"""
voz_civica/respond/base.py

Contrato base (ABC) para backends de geração de resposta — mesmo Adapter
Pattern de civic_framework/adapters/base.py. Por decisão do usuário, a
única implementação real é local (Ollama, sem nuvem, sem custo), mas a
interface já fica pronta pra outro backend entrar depois sem redesenho.

Usado a partir do Estágio 4 do plano — ainda não instanciado nos Estágios
1-2 (só captura+log).
"""

from abc import ABC, abstractmethod
from typing import Optional, Sequence


class ResponderBackend(ABC):
    """Interface abstrata para geração de resposta a partir do histórico da conversa."""

    @abstractmethod
    def generate_reply(
        self, conversation_history: Sequence[dict], extra_instructions: Optional[str] = None
    ) -> str:
        """
        conversation_history: lista de {"role": "user"|"assistant", "content": str},
        em ordem cronológica. Retorna o texto da próxima resposta da IA.

        extra_instructions: orientação dinâmica válida só pra essa chamada
        (ex: "ainda falta perguntar o bairro") — não é persistida em
        conversation_history, é sempre recalculada a cada turno com base no
        estado atual da denúncia (voz_civica.respond.extractor).
        """
