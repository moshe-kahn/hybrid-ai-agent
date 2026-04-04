# Hybrid AI Agent

A lightweight Python CLI agent that routes user input between deterministic computation, language model reasoning, and external tools.

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
  * Supports natural language math such as `twenty-two plus five`

* **Spell correction preprocessing**

  * Fixes minor typos before routing
  * Preserves numbers and operators

* **Hybrid routing**

  * LLM decides between direct response and tool usage

* **Search integration**

  * Uses DuckDuckGo for external queries

* **Runtime configuration**

  * `--mode normal` defaults to friendly output with API-backed LLM calls
  * `--mode debug` defaults to verbose output with local-only behavior
  * `--output verbose` enables internal status logging without changing mode
  * `--connection local` skips LLM calls without changing mode

* **Interactive CLI controls**

  * `s` stops a running query and returns to the prompt
  * `q`, `quit`, or `exit` quits the program

* **Built-in self test**

  * Verifies API key presence, connectivity, model access, and response generation
  * Uses the same `[PASS]` / `[FAIL]` style as the smoke test

* **Shared logging**

  * Writes run output to `logs/latest.log`
  * Supports an optional extra append log via `--log-file`

---

## Architecture

```text
User Input
  ->
Spell Correction
  ->
Routing Logic
  |- Calculator (deterministic)
  |    |- success -> return result
  |    `- failure -> LLM fallback when API connection is enabled
  `- LLM Router
       |- search_tool -> tool -> LLM synthesis
       `- none -> direct response
```

---

## Example Usage

### Math

```text
>> twenty-two plus five
27
```

### Definition

```text
>> what is FastAPI
FastAPI is a modern...
```

### External Query

```text
>> news today
[uses search + LLM synthesis]
```

### Debug-Style Local Behavior

```text
>> 2++
Error in calculation: invalid syntax
```

---

## Modes

Selected from the command line:

```text
py main.py --mode normal
py main.py --mode debug
py main.py --mode normal --output verbose
py main.py --mode normal --connection local
```

Default resolution:

* `--mode normal` -> `--output friendly` + `--connection api`
* `--mode debug` -> `--output verbose` + `--connection local`

You can override `--output` or `--connection` explicitly when you want a mixed configuration.

---

## Project Structure

```text
main.py         # CLI entry point
agent.py        # routing + orchestration
math_utils.py   # parsing + detection
tools.py        # calculator + search
scripts/        # smoke tests
docs/           # project memory and design notes
logs/           # latest run log
```

---

## Tech Stack

* Python
* OpenAI API via `httpx`
* DuckDuckGo via `requests`
* `word2number`
* `pyspellchecker`
* `python-dotenv`

---

## Setup

1. Create a virtual environment.
2. Install dependencies:

   ```text
   pip install -r requirements.txt
   ```

3. Create a `.env` file:

   ```text
   OPENAI_API_KEY=your_key_here
   ```

---

## Run

```text
py main.py
```

Useful variants:

```text
py main.py --mode normal --output verbose
py main.py --mode debug
py main.py --log-file logs/session.log
```

### Self Test

```text
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
* Make behavior debuggable via execution modes and output/connection overrides

---

## Future Improvements

* Better search provider support
* Multi-step tool chaining
* Conversation memory
* Expanded math support
* Structured output enforcement

---

## License

MIT
