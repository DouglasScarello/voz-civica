"""
voz_civica/respond/extractor.py

Extrai um relato cidadão estruturado da conversa — numa chamada TOTALMENTE
SEPARADA da que gera a resposta falada — e detecta quando o cidadão
confirmou que o resumo lido de volta está correto.

Escopo amplo de propósito: não é só reclamação de infraestrutura (buraco na
rua, poste caído) — também cobre opinião sobre lei/política pública
("concordo/discordo de tal lei") e necessidade de serviço ("falta posto de
saúde no bairro X"). O esquema é genérico o suficiente pra cobrir os três
sem exigir campo que não faz sentido pro tipo (ex: opinião sobre lei não
precisa de endereço).

Isso é a peça central da regra de privacidade do usuário: a IA que fala com
a pessoa nunca vê o que foi extraído/gravado de OUTRAS conversas. O que ela
recebe de volta (via `extra_instructions` em ResponderBackend) é só o
estado ATUAL do relato DESSA MESMA conversa — nunca de outra pessoa — pra
saber o que ainda falta perguntar.
"""

import json
from dataclasses import dataclass
from typing import List, Optional, Sequence

import ollama

# Campos sempre exigidos pra considerar o relato "completo", independente do tipo.
CAMPOS_OBRIGATORIOS = ["tipo_relato", "tema", "descricao"]
# Campos que existem mas só fazem sentido pedir dependendo do tipo (a IA decide
# via prompt, não é bloqueado no código — evita perguntar endereço pra opinião
# sobre lei, ou posição concorda/discorda pra buraco na rua).
CAMPOS_OPCIONAIS = ["local", "posicao"]

CAMPOS_LABELS = {
    "tipo_relato": "tipo de relato",
    "tema": "assunto específico",
    "descricao": "descrição do que a pessoa quer dizer",
    "local": "local (rua/bairro), se for algo físico",
    "posicao": "se concorda ou discorda, se for opinião sobre lei/política",
}

EXTRACTION_PROMPT = """\
Você é um extrator de dados, não um assistente de conversa. Leia a conversa
abaixo entre um cidadão e um assistente de voz, e extraia SOMENTE o que o
CIDADÃO relatou — ignore qualquer coisa que o assistente tenha dito.

O relato pode ser de qualquer um destes tipos (ou outro que fizer sentido):
- reclamação de infraestrutura (ex: buraco na rua, poste caído, iluminação)
- opinião sobre lei ou política pública (ex: concorda/discorda de uma lei)
- necessidade de serviço público (ex: falta escola, hospital, posto de saúde)
- outro tipo de demanda cidadã que não se encaixe nos anteriores

Responda em JSON estrito, só com estas chaves:
{{
  "tipo_relato": "...",
  "tema": "...",
  "descricao": "...",
  "local": "...",
  "posicao": "..."
}}

- "tipo_relato": uma das categorias acima (ou outra palavra curta que descreva).
- "tema": o assunto específico (ex: "buraco na rua", "Lei X", "falta de posto de saúde").
- "descricao": resumo do que a pessoa disse sobre esse tema.
- "local": rua/bairro, SÓ se fizer sentido pro tipo (reclamação física). Senão null.
- "posicao": "concorda", "discorda", ou "neutro", SÓ se for opinião sobre lei/política. Senão null.
- Se algum campo não foi mencionado ainda ou não se aplica, use null.
- Se a conversa não descreve nenhum relato concreto ainda, retorne todos os campos como null.

Conversa:
{conversa}
"""

CONFIRMATION_PROMPT = """\
A pessoa disse: "{ultima_fala}"

Isso significa SIM (confirmação/aprovação, ex: "sim", "pode salvar",
"confirmo", "tá certo") ou NAO (negação, correção, dúvida, ou algo não
relacionado)?

Responda só com a palavra SIM ou NAO, nada mais.
"""


@dataclass
class RelatoExtraido:
    tipo_relato: Optional[str] = None
    tema: Optional[str] = None
    descricao: Optional[str] = None
    local: Optional[str] = None
    posicao: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not any([self.tipo_relato, self.tema, self.descricao, self.local, self.posicao])

    @property
    def campos_faltando(self) -> List[str]:
        return [CAMPOS_LABELS[c] for c in CAMPOS_OBRIGATORIOS if not getattr(self, c)]

    @property
    def is_complete(self) -> bool:
        return len(self.campos_faltando) == 0

    def resumo_legivel(self) -> str:
        partes = []
        if self.tipo_relato:
            partes.append(f"Tipo: {self.tipo_relato}")
        if self.tema:
            partes.append(f"Tema: {self.tema}")
        if self.descricao:
            partes.append(f"Descrição: {self.descricao}")
        if self.local:
            partes.append(f"Local: {self.local}")
        if self.posicao:
            partes.append(f"Posição: {self.posicao}")
        return " | ".join(partes) if partes else "(nada coletado ainda)"


def _conversa_como_texto(conversation_history: Sequence[dict]) -> str:
    return "\n".join(
        f"{'Cidadão' if m['role'] == 'user' else 'Assistente'}: {m['content']}"
        for m in conversation_history
    )


def _chat_json(model: str, prompt: str) -> dict:
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], format="json")
    try:
        return json.loads(response["message"]["content"])
    except (json.JSONDecodeError, KeyError):
        return {}


class RelatoExtractor:
    def __init__(self, model: str):
        self._model = model

    def extract(self, conversation_history: Sequence[dict]) -> RelatoExtraido:
        conversa_texto = _conversa_como_texto(conversation_history)
        data = _chat_json(self._model, EXTRACTION_PROMPT.format(conversa=conversa_texto))
        campos = CAMPOS_OBRIGATORIOS + CAMPOS_OPCIONAIS
        # O modelo às vezes devolve a string "null" em vez do JSON null real.
        valores = {c: data.get(c) for c in campos}
        valores = {c: (None if isinstance(v, str) and v.strip().lower() == "null" else v) for c, v in valores.items()}
        return RelatoExtraido(**valores)

    def check_confirmation(self, conversation_history: Sequence[dict]) -> bool:
        """
        Classifica só a ÚLTIMA fala do cidadão como confirmação ou não —
        não depende do texto da IA ter perguntado corretamente (modelos
        pequenos nem sempre seguem a instrução de resumir+perguntar à
        risca; o código já sabe, pelo próprio estado, que essa pergunta
        deveria ter sido feita).

        Usa saída em TEXTO LIVRE (SIM/NAO), não `format="json"`: testado na
        prática, o llama3.2:3b com JSON forçado retorna {"confirmado":
        false} pra qualquer entrada, inclusive "sim" isolado — bug real do
        modo JSON desse modelo com campo booleano. Em texto livre ele
        raciocina certo.
        """
        ultima_fala_usuario = next(
            (m["content"] for m in reversed(conversation_history) if m["role"] == "user"), ""
        )
        prompt = CONFIRMATION_PROMPT.format(ultima_fala=ultima_fala_usuario)
        response = ollama.chat(model=self._model, messages=[{"role": "user", "content": prompt}])
        return "sim" in response["message"]["content"].strip().lower()
