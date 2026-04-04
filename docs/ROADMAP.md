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

**Goal:**

* Reduce ambiguity
* Increase control and interactivity

---

### 2. Calculator Mode (Deterministic + API fallback)

In calculator mode:

1. Try local Python evaluation
2. If it fails → send to Wolfram Alpha
3. If that fails → stop and return error

**Do NOT fallback to LLM in forced calculator mode**

**Goal:**

* Make calculator behavior predictable and trustworthy

---

### 3. Stateful Tool Sessions

Enable tool-specific memory.

Example:

```
2+2 → 4
+3 → 7
```

Future extensions:

* quiz score tracking
* dictionary history
* interactive modes

---

### 4. Runtime Mode Switching

Support:

* CLI flags:

  ```
  py main.py --mode debug
  ```
* In-session commands:

  ```
  /mode verbose
  ```

---

### 5. Model Alias Configuration

Move model selection into config.

Example:

* `ai-lite` → fast/cheap model
* `ai-heavy` → more capable model

Sources:

* `.env`
* config file

**Goal:**

* Decouple code from model names
* Enable easy switching

---

### 6. Token Usage Reporting (Verbose Mode)

Display:

* model used
* input tokens
* output tokens

**Goal:**

* Improve cost visibility
* Support optimization

---

### 7. Better Search / Tool Providers

Replace or augment DuckDuckGo with:

* Brave Search
* Tavily
* Wolfram Alpha (math + conversions)
* Dictionary APIs

**Goal:**

* Use expert tools per domain
* Reduce reliance on LLM

---

## Medium-Term Improvements

* Tool registry system (dynamic tools)
* Multi-provider routing (LLM + APIs + local models)
* Improved math parsing (beyond regex)
* Unit conversion tool
* Confidence scoring for outputs
* Structured logging/tracing
* Retry logic and validation for routing
* Caching repeated queries

---

## Long-Term Improvements

* Conversational memory across sessions
* Multi-step tool chaining
* Planner + executor architecture
* Evaluation / benchmarking framework
* Web interface (FastAPI)
* Self-correction loop

---

## Experimental Ideas

* Hybrid local + cloud LLM system (Ollama + API)
* Automatic tool selection based on query classification
* Cost-aware routing (choose cheaper model/tool)
* Prompt optimization based on past performance

---

## Guiding Principle

The goal is not to build a chatbot, but a **hybrid agent system** that:

* Uses deterministic code where possible
* Uses specialized APIs where appropriate
* Uses LLMs selectively
* Exposes its reasoning and cost in developer-facing modes
