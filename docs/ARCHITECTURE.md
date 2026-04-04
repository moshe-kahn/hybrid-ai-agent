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
       |- search_tool -> tool -> LLM synthesis
       `- none -> direct LLM response
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

Design goals:

* Keep routing simple and inspectable
* Avoid over-reliance on LLM for deterministic tasks

---

### 4. Tool Layer

Current tools:

* `search_tool` (DuckDuckGo)
* `calculator_tool` (local)

Pattern:

```text
LLM -> tool -> LLM
```

---

### 5. Runtime Configuration

Controlled via:

```python
MODE = "normal" | "debug"
OUTPUT = "friendly" | "verbose"
CONNECTION = "api" | "local"
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
  * routing decisions
  * tool calls
  * wait status
  * raw LLM output

Connection layer:

* `api` allows direct `httpx` calls to `/v1/responses`
* `local` skips LLM calls and returns local-mode messages or errors instead

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
* JSON parsing for routing can fail
* No confidence scoring or validation
* Logging is lightweight and file-based rather than structured tracing

---

## Future Architectural Direction

* Tool registry
* Multi-provider routing
* Planner/executor split
* Stateful sessions
* Structured outputs for routing reliability
