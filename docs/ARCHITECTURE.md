# Architecture

## Overview

This project implements a hybrid agent that routes user input between:

* Deterministic computation (calculator)
* Language model reasoning (LLM)
* External tools (search)

The system prioritizes correctness and efficiency by using non-LLM paths whenever possible.

---

## Execution Pipeline

```
User Input
    ↓
Spell Correction (local)
    ↓
Routing
    ├── Calculator (deterministic)
    │       ├── success → return result
    │       └── failure → LLM fallback (disabled in debug)
    │
    └── LLM Router
            ├── search_tool → tool → LLM synthesis
            └── none → direct LLM response
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

### 2. Calculator Path (Deterministic)

* Triggered via `should_force_calculator()`
* Uses:

  * natural language parsing (`math_utils.py`)
  * AST-based safe evaluation (`tools.py`)

**Behavior:**

* Executes locally when possible
* On failure:

  * normal mode → LLM fallback
  * debug mode → return error directly

---

### 3. LLM Router

* Decides between:

  * direct response
  * tool usage

**Design goals:**

* Keep routing simple and inspectable
* Avoid over-reliance on LLM for deterministic tasks

---

### 4. Tool Layer

Current tools:

* `search_tool` (DuckDuckGo)
* `calculator_tool` (local)

Pattern:

```
LLM → tool → LLM (synthesis)
```

---

### 5. Execution Modes

Controlled via:

```python
MODE = "normal" | "verbose" | "debug"
```

#### Normal

* No internal logs
* Full functionality

#### Verbose

* Prints:

  * corrected input
  * routing decisions
  * tool calls
  * raw LLM output

#### Debug

* Same as verbose
* Disables all LLM calls
* Returns raw calculator/tool errors

---

## Design Principles

* **Deterministic first**

  * Use code when correctness matters (math, parsing)

* **LLM as coordinator**

  * Routing, interpretation, fallback

* **Tool specialization**

  * External APIs handle domain-specific tasks

* **Observability**

  * Verbose/debug modes expose internal behavior

---

## Current Limitations

* Rule-based math parsing is brittle
* No conversational memory
* Tool routing is single-step only
* Search results are shallow
* JSON parsing for routing can fail
* No confidence scoring or validation
* No structured logging (print-based only)

---

## Future Architectural Direction

* Tool registry (dynamic tool discovery)
* Multi-provider routing (LLM + APIs)
* Planner/executor split
* Stateful sessions (tool-specific memory)
* Structured outputs for routing reliability
