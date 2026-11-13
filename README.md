# 🎙️ voz-civica — Captação de demanda cidadã por voz, 100% local

Assistente de voz de mão dupla: escuta contínua, transcreve, responde com LLM local e fala a resposta. Sem nuvem, sem API paga, sem custo recorrente — tudo roda na máquina (Silero VAD + faster-whisper + Ollama + Piper).

> 🌱 **Projeto em início de desenvolvimento — Marco 1 de uma visão maior.**
> A camada de captura e conversa funciona de ponta a ponta em teste local (áudio → transcrição → resposta → voz). As camadas de agregação, decisão e transparência pública ainda não existem. CLI, arquitetura interna e formato dos dados **podem mudar sem aviso**.

---

## 📌 Status do Projeto

**Marco 1 — captura e conversa** (em andamento, funcional)

| Estágio | Implementado | Validado |
|---|:--:|---|
| Captura contínua com detecção de fala (VAD) | ✅ | ✅ com arquivo `.wav` — microfone real: ⚠️ não testado |
| Transcrição local (faster-whisper, `small`/`int8`, pt-BR) | ✅ | ✅ ponta a ponta, com áudio real |
| Resposta via LLM local (Ollama) | ✅ | ✅ ponta a ponta, com Ollama rodando |
| Síntese de voz (Piper) com anti-feedback | ✅ | ✅ gera e reproduz — **anti-feedback com mic + caixa: ⚠️ não validado** |
| UI pulsante no navegador (FastAPI + WebSocket) | ✅ | ✅ servidor, botões e amplitude verificados por script |
| Órbita reagindo à voz da IA (amplitude real do TTS) | ✅ | ✅ 326 amostras de amplitude em execução real |
| Extração estruturada do relato (fila de backend) | ✅ | ⚠️ só testes unitários — 0 relatos gravados em execução real |
| Interrupção da fala da IA (*barge-in*) | ❌ | — previsto, não implementado |

**Última execução de ponta a ponta:** 13/11/2026, Arch Linux, CPU, sobre `tests/fixtures/sample_speech.wav` (2,5 s de áudio). Comando: `voz-civica capture --file ... --respond`. A UI foi verificada subindo `voz-civica live`, mas **sem conversa por microfone**.

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

## 🖥️ Interface

Uma bola. Três botões. Nada mais.

O orb **pulsa apenas com a voz da IA**: durante a reprodução, o áudio do Piper é tocado em blocos de 50 ms, a amplitude (RMS) de cada bloco é normalizada pelo pico da própria fala e publicada por WebSocket a 25 Hz. Fora da fala a amplitude é 0.0 — o microfone **não** move a bola, ele só alimenta o pipeline.

| Cor | Estado |
|---|---|
| Azul | ouvindo (respiração lenta) |
| Âmbar | pensando (espera real do LLM) |
| Verde | falando (pulso = volume real da voz) |
| Cinza | pausado |

| Botão | Ação | Atalho |
|---|---|---|
| pausar / retomar | para de processar fala do microfone (frames continuam sendo consumidos) | `espaço` |
| silenciar voz / ativar voz | gera a resposta mas não fala em voz alta | `M` |
| parar fala | interrompe a reprodução no meio (checado entre blocos) | `Esc` |

Para ver a interface sem microfone, rodando sobre o áudio de teste:

```bash
poetry run voz-civica live --file tests/fixtures/sample_speech.wav --speak
```

---

## 📊 Números medidos

- **18 testes automatizados**, todos passando (`pytest -q`).
- **25 módulos Python**, ~1.752 linhas de aplicação + 358 linhas de teste.
- **Transcrição: ~1,6–1,9 s** para 2,5 s de áudio (faster-whisper `small`, `int8`, CPU) — medido em 13/11/2026.
- **Orb: 326 amostras de amplitude** na fala de uma resposta, 86 níveis distintos, 24% no topo — medido via WebSocket.
- **0 chamadas a serviços externos pagos** — Ollama, Whisper e Piper rodam na máquina.
- **0 credenciais** necessárias para rodar.
- **Latência de ponta a ponta (fim da fala → início da resposta falada): não medida ainda** (ver Limitações).

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
# 18 passed
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
│   ├── ui/           # Servidor FastAPI + orb pulsante e botões (WebSocket)
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

- **Nenhuma conversa por microfone foi feita ainda**: toda a validação de ponta a ponta usou um arquivo `.wav`. O caminho `MicrophoneSource` existe e tem teste unitário, mas não foi exercitado ao vivo.
- **Sem *barge-in***: não é possível interromper a IA no meio da fala. Limitação conhecida da versão 0.1, não bug.
- **Anti-feedback não validado em cenário real**: `drain_pending` foi implementado e testado com arquivo, mas o caso crítico — mic aberto enquanto a caixa de som toca, sem headset — ainda não foi confirmado em execução real.
- **Latência de ponta a ponta não medida**: só o estágio de transcrição tem número (~1,6–1,9 s para 2,5 s de áudio). Não existe medição do tempo entre o fim da fala e o início da resposta falada.
- **Extração de relato não exercitada em execução real**: o pipeline gravou 2 sessões no SQLite, mas **0 relatos** — o extrator só tem cobertura de teste unitário.
- **Interface verificada por script, não a olho**: a amplitude do orb e os três botões foram validados por cliente WebSocket (326 amostras, 86 níveis) e os testes rodam sem placa de som. **O visual em si não foi conferido manualmente no navegador.**
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
