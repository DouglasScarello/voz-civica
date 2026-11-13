# voz-civica

Assistente de voz local, de mão dupla — escuta contínua, transcrição, resposta via LLM local e síntese de voz. **100% offline, 100% de graça, sem nuvem.**

Marco 1 de uma visão maior: um pipeline de captação de demanda cidadã que, no futuro, alimenta camadas de agregação, decisão e transparência pública. Aqui só a camada de captura/conversa está sendo construída.

## Por que local, não nuvem

Sem financiamento e sem custo recorrente por design — e mesmo antes de existirem dados sensíveis de verdade, o projeto já segue o princípio de manter tudo auditável e sob controle próprio, porque essa é a base de algo que pode crescer depois.

## Arquitetura

```
Microfone → VAD (Silero) → Transcrição (faster-whisper) → Resposta (Ollama local)
   → Síntese de voz (Piper) → Reprodução → volta a escutar
```

Cada turno é registrado (áudio, transcrição, resposta, tempos) em log JSON datado + SQLite com trilha de auditoria.

## Requisitos

- Python 3.12 (via `uv python install 3.12`, veja abaixo)
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/) instalado e com um modelo puxado (`ollama pull llama3.2:3b`)
- Uma voz do Piper baixada (`poetry run python scripts/download_piper_voice.py pt_BR-faber-medium`)
- Microfone funcional

## Setup

```bash
# 1. Python 3.12 (a máquina só vem com 3.14 por padrão)
sudo pacman -S uv        # único passo que precisa de root
uv python install 3.12

# 2. Ambiente do projeto
poetry env use "$(uv python find 3.12)"
poetry install

# 3. Voz do Piper (uma vez só)
poetry run python scripts/download_piper_voice.py pt_BR-faber-medium
```

## Uso

```bash
# Só escuta e transcreve, imprime no terminal
poetry run voz-civica capture

# + resposta via LLM local (texto, sem áudio)
poetry run voz-civica capture --respond

# + fala a resposta em voz alta (conversa completa, mão dupla)
poetry run voz-civica capture --speak

# Mesma coisa, mas com a UI pulsante no navegador
poetry run voz-civica live --speak
# abre http://127.0.0.1:8000

# Rodar sobre um arquivo .wav em vez do microfone (não pede --speak sair pela caixa,
# mas ainda sintetiza e toca — útil pra testar sem depender de gravação nova)
poetry run voz-civica capture --file caminho/audio.wav --speak
```

Flags úteis: `--model` (troca o modelo do Ollama), `--voice` (troca a voz do Piper), `--device` (escolhe o microfone), `--host`/`--port` (só no `live`).

## Status

Todos os estágios do Marco 1 implementados: captura contínua (VAD), transcrição, resposta via LLM local, síntese de voz com anti-feedback, e UI pulsante. Sem barge-in (não dá pra interromper a IA no meio da fala) nessa primeira versão — é a limitação conhecida, não bug.

**Ainda não validado com microfone + caixa de som reais ao mesmo tempo** — o anti-feedback (`drain_pending`) foi implementado e testado com arquivo, mas o cenário real (IA falando pela caixa enquanto o mic tá aberto, sem headset) só se confirma rodando de verdade: `poetry run voz-civica live --speak`, testando se ela nunca se autoescuta.

## Licença

MIT — ver [LICENSE](LICENSE).
