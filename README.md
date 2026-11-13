# 🎙️ voz-civica — Captação de demanda cidadã por voz, 100% local

Assistente de voz de mão dupla: escuta contínua, transcreve, responde com LLM local e fala a resposta. Sem nuvem, sem API paga, sem custo recorrente — tudo roda na máquina (Silero VAD + faster-whisper + Ollama + Piper).

> 🌱 **Projeto em início de desenvolvimento — Marco 1 de uma visão maior.**
> A camada de captura e conversa está funcional e testada; as camadas de agregação, decisão e transparência pública ainda não existem. CLI, arquitetura interna e formato dos dados **podem mudar sem aviso**.

---

## 📌 Status do Projeto

**Marco 1 — captura e conversa** (em andamento, funcional)

| Estágio | Implementado | Validado |
|---|:--:|---|
| Captura contínua com detecção de fala (VAD) | ✅ | ✅ testes automatizados |
| Transcrição local (faster-whisper, `small`/`int8`, pt-BR) | ✅ | ✅ com fixture de áudio real |
| Resposta via LLM local (Ollama) | ✅ | ✅ com Ollama rodando |
| Síntese de voz (Piper) com anti-feedback | ✅ | ⚠️ só com arquivo — **não validado com mic + caixa simultâneos** |
| UI pulsante no navegador (FastAPI + SSE) | ✅ | ✅ local |
| Extração estruturada do relato (fila de backend) | ✅ | ✅ testes automatizados |
| Interrupção da fala da IA (*barge-in*) | ❌ | — previsto, não implementado |

**Marcos seguintes** (não iniciados): agregação dos relatos, priorização, painel público de transparência.

---

## 🏛️ Pilares Arquiteturais

### 1. 🎤 Captura: VAD Silero em tempo real
- **Frames de 512 amostras** a 16 kHz (~32 ms) — tamanho nativo do modelo.
- **Máquina de estados explícita**: `SPEECH_START` após 3 frames acima do limiar, `SPEECH_END` após 800 ms de silêncio.
- **Pré-roll de 250 ms**: o áudio anterior ao início da fala é preservado, para não cortar a primeira sílaba.

### 2. 📝 Transcrição: faster-whisper local
- **`small` em `int8` na CPU**: escolha por custo zero e privacidade, não por benchmark.
- **Idioma fixo em pt-BR** com `initial_prompt` de vocabulário cívico (buraco, poste, calçada, esgoto) — reduz confusão do modelo com palavras parecidas em inglês.

### 3. 🧠 Resposta: Ollama local
- **Sem chave de API**: o projeto não usa nenhum serviço pago por design.
- **Modelo padrão `llama3.2:3b`**, trocável por `--model`.
- **Extração separada da conversa**: o relato estruturado é gerado por um extrator que nunca é lido de volta pela IA.

### 4. 🔊 Síntese e anti-feedback: Piper
- **Voz `pt_BR-faber-medium`**, baixada sob demanda (não versionada).
- **`drain_pending`**: descarta o áudio capturado enquanto a IA fala, para ela não se autoescutar.
- **Reprodução bloqueante por turno**: o microfone só volta a valer depois do fim da fala.

---

## 📊 Números medidos

- **10 testes automatizados**, todos passando (`pytest -q`).
- **25 módulos Python**, ~1.590 linhas de aplicação + 208 linhas de teste.
- **0 chamadas a serviços externos pagos** — Ollama, Whisper e Piper rodam na máquina.
- **0 credenciais** necessárias para rodar.
- **Latência de ponta a ponta: não medida ainda** (ver Limitações).

---

## 🚀 Início Rápido

### Pré-requisitos
- Python **3.12** (o projeto não roda na 3.14)
- [Poetry](https://python-poetry.org/)
- [Ollama](https://ollama.com/) com um modelo baixado: `ollama pull llama3.2:3b`
- Microfone funcional (ou um arquivo `.wav` para testar sem mic)

### Instalação
```bash
# 1. Clone
git clone https://github.com/DouglasScarello/voz-civica.git
cd voz-civica

# 2. Python 3.12 (via uv — único passo que pede root)
sudo pacman -S uv        # Arch/Manjaro; use o equivalente da sua distro
uv python install 3.12

# 3. Ambiente e dependências
poetry env use "$(uv python find 3.12)"
poetry install

# 4. Voz do Piper (uma vez só, ~61 MB, não versionada)
poetry run python scripts/download_piper_voice.py pt_BR-faber-medium
```

### Execução
```bash
# Só escuta e transcreve, imprime no terminal
poetry run voz-civica capture

# + resposta via LLM local (texto, sem áudio)
poetry run voz-civica capture --respond

# + fala a resposta (conversa completa, mão dupla)
poetry run voz-civica capture --speak

# Com a UI pulsante no navegador (abre http://127.0.0.1:8000)
poetry run voz-civica live --speak

# Sobre um arquivo .wav, sem depender de microfone
poetry run voz-civica capture --file caminho/audio.wav --speak
```

### Testes
```bash
poetry run pytest -q
# 10 passed
```

---

## 🎛️ Comandos e Flags

| Comando / flag | Função |
|---|---|
| `capture` | Escuta contínua + transcrição (opcionalmente resposta e fala) |
| `live` | Igual ao `capture`, com UI pulsante no navegador |
| `--respond` | Gera resposta via Ollama após cada transcrição |
| `--speak` | Fala a resposta via Piper (implica `--respond`) |
| `--file <path>` | Roda o pipeline sobre um `.wav` em vez do microfone |
| `--model <nome>` | Troca o modelo do Ollama (padrão: `llama3.2:3b`) |
| `--voice <nome>` | Troca a voz do Piper (padrão: `pt_BR-faber-medium`) |
| `--device <índice>` | Seleciona o dispositivo de captura |
| `--host` / `--port` | Endereço da UI (só no `live`; padrão `127.0.0.1:8000`) |

Configuração avançada (limiares do VAD, modelo do Whisper, prompt inicial) fica em `voz_civica/config.py` e aceita override por variável de ambiente com prefixo `VOZ_CIVICA_`.

---

## 📂 Estrutura do Projeto

```text
├── voz_civica/
│   ├── audio/        # Captura, VAD, reprodução e fontes (mic / arquivo)
│   ├── stt/          # Transcrição local com faster-whisper
│   ├── respond/      # Resposta via Ollama + extração do relato
│   ├── tts/          # Síntese de voz com Piper
│   ├── session/      # Registro do turno: log JSON + SQLite com auditoria
│   ├── ui/           # Servidor FastAPI + UI pulsante (SSE)
│   ├── config.py     # Configuração central (pydantic-settings)
│   ├── orchestrator.py # Encadeia captura → STT → resposta → fala
│   └── cli.py        # Ponto de entrada (argparse)
├── scripts/          # Download da voz do Piper
├── tests/            # 10 testes + fixture de áudio real
├── data/             # Áudio e sessões em runtime (não versionado)
├── models/           # Voz do Piper (~61 MB, não versionada)
└── pyproject.toml    # Dependências e entrypoint
```

---

## 📑 Limitações e Transparência

- **Sem *barge-in***: não é possível interromper a IA no meio da fala. Limitação conhecida da versão 0.1, não bug.
- **Anti-feedback não validado em cenário real**: `drain_pending` foi testado com arquivo, mas o caso crítico — mic aberto enquanto a caixa de som toca, sem headset — ainda não foi confirmado em execução real.
- **Latência não medida**: nenhum benchmark de tempo de resposta foi publicado. Não há número de "tempo até a primeira palavra" neste README porque ele não foi medido.
- **Apenas pt-BR** e apenas CPU.
- **UI sem autenticação**: o servidor `live` escuta em `127.0.0.1` e não deve ser exposto na rede.
- **Sem CI, sem lint automatizado e sem empacotamento** (não está no PyPI; roda via `poetry`).
- **Sem camada de agregação**: hoje cada conversa é registrada isoladamente; não existe visão consolidada dos relatos.

---

## 🗺️ Próximos Passos

1. Validar o anti-feedback com microfone e caixa reais.
2. Medir e publicar latência por estágio (VAD → STT → LLM → TTS).
3. Implementar *barge-in*.
4. Agregar os relatos em uma primeira visão consolidada.
5. Adicionar CI (pytest + ruff) no GitHub Actions.

---

## ⚖️ Licença

MIT — ver [LICENSE](LICENSE).

**Marco 1 funcional e testado; o resto do caminho está declarado acima.** 🌱
