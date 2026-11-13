"""
tests/test_respond.py

Testa o OllamaResponder de verdade — Ollama já roda localmente nessa
máquina como serviço de sistema (sem dependência de rede externa, consistente
com a filosofia 100% local do projeto). Mais lento que os outros testes
(~5-15s) por chamar o modelo de verdade, de propósito: não tem sentido
mockar a única peça que a gente mais precisa validar aqui.
"""

from voz_civica.config import settings
from voz_civica.respond.local_llm import OllamaResponder


def test_generates_non_empty_reply():
    responder = OllamaResponder(model=settings.ollama_model)
    reply = responder.generate_reply([{"role": "user", "content": "Oi, você está aí?"}])

    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
