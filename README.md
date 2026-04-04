# Hybrid AI Agent

A lightweight Python agent that routes user input between deterministic computation, language model reasoning, and external tools.

---

## Overview

This project implements a hybrid agent architecture that avoids sending every query directly to an LLM. Instead, it combines rule-based logic with model-based reasoning to choose the most appropriate execution path.

The system prioritizes:

* **Deterministic computation** for math
* **Tool usage** for external data
* **LLM reasoning** for interpretation and fallback

---

## Features

* **Calculator-first execution**

  * Evaluates math locally using a safe AST parser
  * Supports natural language math (e.g. `twenty-two plus five`)

* **Spell correction preprocessing**

  * Fixes minor typos before routing
  * Preserves numbers and operators

* **Hybrid routing**

  * LLM decides between:

    * direct response
    * tool usage (search)

* **Search integration**

  * Uses DuckDuckGo for external queries

* **Execution modes**

  * `normal` — clean output with a compact waiting indicator
  * `verbose` — shows internal steps
  * `debug` — disables LLM calls (for testing)

* **Interactive CLI controls**

  * `s` stops a running query and returns to the prompt
  * `q`, `quit`, or `exit` quits the program

* **Built-in self test**

  * Verifies API key presence, connectivity, model access, and response generation

* **Error handling**

  * Graceful API fallback
  * Transparent calculator errors in debug mode

---

## Architecture

```
User Input
    ↓
Spell Correction
    ↓
Routing Logic
    ├── Calculator (deterministic)
    │       ├── success → return result
    │       └── failure → LLM fallback
    │
    └── LLM Router
            ├── search_tool → tool → LLM synthesis
            └── none → direct response
```

---

## Example Usage

### Math

```
>> twenty-two plus five
27
```

### Definition

```
>> what is FastAPI
FastAPI is a modern...
```

### External query

```
>> news today
[uses search + LLM synthesis]
```

### Debug mode

```
>> 2++
Error in calculation: invalid syntax
```

---

## Modes

Selected from the command line:

```
py main.py --mode normal
py main.py --mode verbose
py main.py --mode debug
```

If no `--mode` is provided, the app keeps its default behavior.

---

## Project Structure

```
main.py         # CLI entry point
agent.py        # routing + orchestration
math_utils.py   # parsing + detection
tools.py        # calculator + search
```

---

## Tech Stack

* Python
* OpenAI API
* DuckDuckGo (requests)
* word2number
* pyspellchecker
* python-dotenv

---

## Setup

1. Create a virtual environment
2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file:

   ```
   OPENAI_API_KEY=your_key_here
   ```

---

## Run

```
py main.py
```

### Self Test

```
py main.py --self-test
```

This runs a progressive check of:

* API key presence
* DNS resolution
* raw HTTPS access
* authenticated model access
* model availability
* response generation

### While Running

* Press `s` during a request to stop waiting and return to the prompt
* Press `q` during a request to quit immediately
* Type `q`, `quit`, or `exit` at the prompt to quit

---

## Design Goals

* Use deterministic logic where possible
* Use LLMs for reasoning, not everything
* Keep components modular and inspectable
* Make behavior debuggable via execution modes

---

## Future Improvements

* Better search provider (Brave, Tavily)
* Multi-step tool chaining
* Conversation memory
* Expanded math support (functions, units)
* Structured output enforcement

---

## License

MIT
