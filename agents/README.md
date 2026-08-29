# `agents/` — local Ollama side-car

Scripts for running the project's generative work against a **local Ollama
server** instead of Groq. Built for the two-laptop setup: the model runs on a
machine with a GPU, these scripts run here and talk to it over the network.

## What this is not

- **It is not `src/researchgpt/agents/`.** That package holds the six pipeline
  agents. This folder is experiment scripts, outside the installed package, and
  nothing in the pipeline imports it.
- **It does not change the web app.** The FastAPI server and the Vue frontend
  still talk to Groq exactly as before. No config, no route, no component was
  touched. Running anything in here has no effect on `npm run dev`.
- **It does not change `configs/default.yaml`** or the `ALLOWED_MODELS`
  allowlist. See *Wiring it in* at the bottom for what that would take.

## $0 status

A locally served open-weight model costs nothing and has no tier to fall off,
so this satisfies TASKLIST §0.1 on its own terms. It is arguably *more*
compliant than the hosted path: there is no daily budget, no rate limit, and no
provider that can change its pricing mid-project. The allowlist is untouched
because these scripts bypass `core/llm.py` entirely rather than widening it.

---

## Setup

### On the machine with the GPU

```bash
# 1. install Ollama, then bind it to 8080 on all interfaces so the other
#    laptop can reach it. Ollama's own default is 11434 and 127.0.0.1 only.
#    Windows:  setx OLLAMA_HOST "0.0.0.0:8080"   (then restart Ollama)
#    Linux/mac:
OLLAMA_HOST=0.0.0.0:8080 ollama serve

# 2. pull a model that fits the card (see the table below)
ollama pull qwen2.5:3b-instruct

# 3. find the LAN address to hand to the other laptop
ipconfig        # Windows  -> IPv4 Address
ip addr         # Linux
```

Windows Firewall will block inbound 8080 by default. Allow it for private
networks, or nothing will connect.

### On this machine

```bash
pip install -e ".[retrieval]"     # or nothing at all — the path bootstrap in
                                  # __init__.py finds src/ on its own

export OLLAMA_HOST=http://192.168.1.7:8080     # the friend's laptop, not localhost
export OLLAMA_MODEL=qwen2.5:3b-instruct

python -m agents.probe
```

`localhost:8080` only works if Ollama is on **this** machine. Across two
laptops it must be the server's LAN IP.

## Model choice for a 5 GB card

q4_K_M weights. The KV cache for `num_ctx 8192` adds roughly 0.3–0.8 GB on top,
which is why the 7B row is "tight" rather than "fine" — it fits the weights but
not the weights plus a usable context window.

| model | ~VRAM | verdict |
|---|---|---|
| `qwen2.5:3b-instruct` | 1.9 GB | **recommended** — best JSON discipline in this size class |
| `llama3.2:3b` | 2.0 GB | comfortable |
| `phi3.5:3.8b` | 2.2 GB | comfortable |
| `gemma2:2b` | 1.6 GB | fits easily, weakest of the set |
| `qwen2.5:7b-instruct` | 4.7 GB | tight — use `--num-ctx 4096` |
| `gemma2:9b` | 5.4 GB | does not fit; partial CPU offload, very slow |
| `gpt-oss:20b` | ~13 GB | **not usable on 5 GB.** The hosted arm's model is out of reach locally |

That last row matters for the report: the model the pipeline actually uses
cannot be reproduced on this hardware, so a local arm is a *different* model,
not a local copy of the hosted one.

## ⚠️ The `num_ctx` trap

**Ollama's default context window is 2048 tokens. The extractor prompt alone is
14,125 characters — about 3,530 tokens — before any paper text is added.**

At the default, Ollama silently drops the front of the prompt (the JSON schema
and the few-shot examples) and answers from whatever survived. There is no
error and no warning; you get confident, well-formed JSON of the wrong shape.

Every client here sets `num_ctx` explicitly to 8192, and `probe.py` verifies it
with a canary planted at the start of a long prompt. If the canary does not come
back, the server is truncating and nothing downstream is trustworthy.

---

## The scripts

### `probe.py` — run this first

```bash
python -m agents.probe
python -m agents.probe --host http://192.168.1.7:8080 --model llama3.2:3b
```

Four checks, stopping at the first failure: server reachable → model present →
context honoured (the canary test) → tokens/sec, with an estimate of how long a
ten-paper extraction will take on this hardware.

### `extract.py` — the real prompt, the real parser

```bash
python -m agents.extract --n 5
python -m agents.extract --run t410_cap25 --n 10
python -m agents.extract --n 5 --max-source-chars 12000 --num-ctx 16384
```

Loads `core/prompts/extractor_v1.md` and `core.llm.extract_json` verbatim, so it
measures the model rather than a re-implementation. Reads papers from a run's
`corpus.json` or from `eval/cache/pool_mps25.json` — no network, no API key.
Reports parse rate, mean fields of 8, placeholder echoes, extracted characters
and latency. Writes to `agents/out/`, never to `outputs/runs/`.

**On `--max-source-chars`.** The pipeline caps the rendered prompt at 18,000
chars because *Groq* 413s over ~20 KB. That limit does not exist locally. The
default here is **3,904** — what the hosted arm actually gets after the
14,125-char template — so comparisons are fair. Raise it only when you mean to
exploit local headroom, and raise `--num-ctx` with it.

### `bakeoff.py` — T-004 for local models

```bash
python -m agents.bakeoff --models qwen2.5:3b-instruct llama3.2:3b phi3.5:3.8b --n 5
```

Same papers across every arm, scored on T-004's criteria in T-004's order:
placeholder echo first (disqualifying — it is fabricated content that parses and
validates), then clean parse rate, field coverage, latency. Prints the recorded
hosted baselines alongside so a local number is read against something real.

---

## Wiring it into the pipeline — not done, deliberately

These scripts stop at measurement. Making the graph itself run on Ollama would
need three changes, none of which are made here:

1. `ALLOWED_MODELS` in `core/models.py` would have to admit the Ollama model
   names, or the config would be rejected at load time. That constant is the
   project's only enforcement of §0.1 — widening it is a decision, not a patch.
2. `core/llm.py` would need an `ollama` branch in `_dispatch` and a matching
   entry in `MODEL_PROVIDER`.
3. `configs/` would need a profile pointing at the local host, and `trace.jsonl`
   would need to record it, so a survey produced locally is never mistakable for
   a Groq artefact.

Do the measurement first. If a 3B model cannot clear the placeholder-echo bar on
five papers, none of the above is worth doing.
