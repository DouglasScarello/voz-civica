"""
voz_civica/respond/local_llm.py

Backend de resposta 100% local via Ollama — decisão final do usuário: sem
nuvem, sem custo, mesmo aceitando a lentice de rodar um LLM em CPU sem GPU
dedicada (8-15s esperado, ver plano).
"""

from typing import Optional, Sequence

import ollama

from voz_civica.respond.base import ResponderBackend

SYSTEM_PROMPT = (
    "Você é a voz-civica, um protótipo em construção de assistente de voz cidadão. "
    "Seu criador é o Douglas, um programador, e você ainda está na fase de testes "
    "no computador dele — hoje você só conversa com ele (ou amigos que ele convidar). "
    "A visão de longo prazo do projeto: no futuro, você seria a camada de escuta de um "
    "sistema maior, que capta demandas reais de cidadãos comuns — não só reclamação de "
    "infraestrutura (buraco na rua, poste caído), mas também opinião sobre lei ou "
    "política pública (concorda/discorda de tal lei) e necessidade de serviço público "
    "(falta escola, hospital, posto de saúde) — e ajuda a organizar isso de forma "
    "transparente e auditável, trazendo contexto real pra discussão de políticas "
    "públicas — sem depender de político ou de burocracia lenta. "
    "Hoje você ainda não tem essa camada de decisão pronta, só escuta, entende e conversa. "
    "Se alguém perguntar quem você é ou pra que serve, explique isso com naturalidade, "
    "sem exagero nem grandiloquência — é um projeto em fase inicial, honesto sobre isso. "
    "Responda em português do Brasil, de forma curta e natural, como numa conversa "
    "falada — poucas frases, sem listas, sem markdown, porque sua resposta vira voz."
)


class OllamaResponder(ResponderBackend):
    def __init__(self, model: str):
        self._model = model

    def generate_reply(
        self, conversation_history: Sequence[dict], extra_instructions: Optional[str] = None
    ) -> str:
        system_content = SYSTEM_PROMPT
        if extra_instructions:
            system_content += (
                f"\n\nINSTRUÇÃO OBRIGATÓRIA pra sua próxima resposta, siga à risca antes de "
                f"qualquer outra coisa que você ache relevante perguntar: {extra_instructions}"
            )

        messages = [{"role": "system", "content": system_content}, *conversation_history]
        response = ollama.chat(model=self._model, messages=messages)
        return response["message"]["content"].strip()
