# Roadmap

## Near-Term Priorities

### 1. Explicit Tool Modes

Allow users to directly enter tools instead of relying only on routing.

Examples:

* `calc` / `calculator`
* `dictionary`
* `quiz`
* `jokes`
* `poems`

Goal:

* Reduce ambiguity
* Increase control and interactivity

---

### 2. Calculator Mode (Deterministic + API fallback)

In calculator mode:

1. Try local Python evaluation.
2. If it fails, send to Wolfram Alpha.
3. If that fails, stop and return an error.

Do not fall back to the LLM in forced calculator mode.

Goal:

* Make calculator behavior predictable and trustworthy

---

### 3. Stateful Tool Sessions

Enable tool-specific memory.

Example:

```text
2+2 -> 4
+3 -> 7
```

Future extensions:

* quiz score tracking
* dictionary history
* interactive modes

---

### 4. Runtime Mode Switching

Support:

* CLI flags:

  ```text
  py main.py --mode debug
  py main.py --mode normal --output verbose
  ```

* In-session commands:

  ```text
  /mode debug
  /output verbose
  ```

---

### 5. Model Alias Configuration

Move model selection into config.

Examples:

* `ai-lite` -> fast/cheap model
* `ai-heavy` -> more capable model

Sources:

* `.env`
* config file

Goal:

* Decouple code from model names
* Enable easy switching

---

### 6. Token Usage Reporting

Display:

* model used
* input tokens
* output tokens

Goal:

* Improve cost visibility
* Support optimization

---

### 7. Better Search / Tool Providers

Replace or augment DuckDuckGo with:

* Brave Search
* Tavily
* Wolfram Alpha
* Dictionary APIs

Goal:

* Use expert tools per domain
* Reduce reliance on LLM

---

### 8. Local LLM Provider (Ollama) With Fallback

Implemented in the current branch in a usable first form. Keep improving it rather than redesigning it.

Current behavior:

* `openai` -> always use OpenAI
* `ollama` -> always use the local model
* `auto` -> try Ollama first, then fall back to OpenAI on eligible failure

Implementation preference:

* Keep the refactor small
* Avoid a broad multi-folder redesign

Still needed:

* improve factual/current lookup enforcement
* keep local-model prompt and timeout behavior practical
* continue improving verbose diagnostics without making terminal output noisy

---

## Medium-Term Improvements

* Tool registry system
* Multi-provider routing
* Improved math parsing
* Unit conversion tool
* Confidence scoring for outputs
* Structured logging and tracing
* Retry logic and validation for routing
* Caching repeated queries

---

## Long-Term Improvements

* Conversational memory across sessions
* Multi-step tool chaining
* Planner and executor architecture
* Evaluation and benchmarking framework
* Web interface
* Self-correction loop

---

## Experimental Ideas

* Hybrid local and cloud LLM system
* Automatic tool selection based on query classification
* Cost-aware routing
* Prompt optimization based on past performance

---

## Guiding Principle

The goal is not to build a chatbot, but a hybrid agent system that:

* Uses deterministic code where possible
* Uses specialized APIs where appropriate
* Uses LLMs selectively
* Exposes its reasoning and cost in developer-facing modes
