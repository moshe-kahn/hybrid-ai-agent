# Architecture

## Overview

This project implements a hybrid agent that routes user input between:

* Deterministic computation (calculator)
* Language model reasoning (LLM)
* External tools (search)

The system prioritizes correctness and efficiency by using non-LLM paths whenever possible.

---

## Execution Pipeline

```text
User Input
  ->
Spell Correction (local)
  ->
Routing
  |- Calculator (deterministic)
  |    |- success -> return result
  |    `- failure -> LLM fallback when API connection is enabled
  `- LLM Router
       |- search_tool -> tool result
       `- none -> direct answer from router JSON
```

---

## Core Components

### 1. Preprocessing Layer

* Spell correction using `pyspellchecker`
* Preserves:

  * numbers
  * operators (`+ - * /`)
* Improves routing and parsing reliability

---

### 2. Calculator Path

* Triggered via `should_force_calculator()`
* Uses:

  * natural language parsing in `math_utils.py`
  * AST-based safe evaluation in `tools.py`

Behavior:

* Executes locally when possible
* On failure:

  * API connection mode -> direct LLM fallback
  * local connection mode -> return calculator error directly

---

### 3. LLM Router

* Decides between:

  * direct response
  * tool usage

Current contract:

* One LLM call returns strict JSON with:
  * `tool`
  * `input`
  * `answer`
* If `tool == "none"`, `answer` is returned directly
* If `tool == "search_tool"`, `input` is sent to DuckDuckGo and the tool result is returned directly

Design goals:

* Keep routing simple and inspectable
* Avoid over-reliance on LLM for deterministic tasks

---

### 4. Tool Layer

Current tools:

* `search_tool` (DuckDuckGo)
* `calculator_tool` (local)
* provider transport and response parsing (`llm_client.py`)

---

### 5. Runtime Configuration

Controlled via:

```python
MODE = "normal" | "debug"
OUTPUT = "friendly" | "verbose"
CONNECTION = "api" | "local"
PROVIDER = "openai" | "ollama" | "auto"
```

Normal mode defaults:

* `OUTPUT = "friendly"`
* `CONNECTION = "api"`
* Compact CLI output with a waiting indicator

Debug mode defaults:

* `OUTPUT = "verbose"`
* `CONNECTION = "local"`
* Skips LLM calls and surfaces local/tool failures directly

Output layer:

* `friendly` keeps the CLI compact
* `verbose` prints:

  * corrected input
  * provider attempts
  * provider success
  * routing decisions for tool-selected requests
  * tool calls
  * wait status

Raw provider payloads and full router output are kept in `logs/latest.log` instead of printed to the terminal.

Connection layer:

* `api` allows direct `httpx` calls to `/v1/responses`
* `local` skips LLM calls and returns local-mode messages or errors instead

Provider layer:

* `openai` selects the hosted OpenAI backend
* `ollama` selects the local Ollama backend
* `auto` tries Ollama first and falls back to OpenAI only on transport, timeout, availability, or empty-output failure when hosted calls are allowed
* `auto` is the current CLI default
* `--timeout` sets the total per-run budget; in `auto`, the provider layer splits that budget between the local attempt and hosted fallback

---

## Design Principles

* **Deterministic first**

  * Use code when correctness matters

* **LLM as coordinator**

  * Routing, interpretation, fallback

* **Tool specialization**

  * External APIs handle domain-specific tasks

* **Observability**

  * Verbose output exposes internal behavior without requiring code changes

---

## Current Limitations

* Rule-based math parsing is brittle
* No conversational memory
* Tool routing is single-step only
* Search results are shallow
* JSON parsing is more tolerant now, but malformed model output can still produce poor routing decisions
* No confidence scoring or validation
* Logging is lightweight and file-based rather than structured tracing
* Factual or current-event questions are not yet enforced deterministically; a local model can still answer directly when policy would prefer search
* Calculator parse failure still uses a direct LLM fallback instead of a dedicated math/search API

---

## Future Architectural Direction

* Tool registry
* Planner/executor split
* Stateful sessions
* Stronger factual/search policy enforcement
* Dedicated calculator fallback such as Wolfram Alpha
