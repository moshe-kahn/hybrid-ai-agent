# Context

This file is the running handoff note for major project updates. Update it whenever a meaningful change lands so the next session has the current context without reconstructing it from chat history.

## Update Convention

- After behavior change: update `CONTEXT.md`
- Before commit:
  - update `SESSION_NOTES.md`
  - update `KNOWN_ISSUES.md` if the test surface changed
- After debugging session:
  - ensure `KNOWN_ISSUES.md` reflects anything fragile or needing re-test

## How To Use This File

When making a major update, refresh these sections:

1. What changed
2. Recent user requests
3. Current short-term goal
4. Known issues and things to verify
5. Suggested next steps

Keep entries brief and practical. Prefer current state over a long historical log.

## Current Snapshot

- Project: hybrid CLI AI agent that routes between calculator logic, search, and LLM reasoning.
- Main entry point: `main.py`
- Core orchestration: `agent.py`
- Math parsing and detection: `math_utils.py`
- Tools: `tools.py`

## What Changed Recently

- Added CLI mode selection and then split runtime behavior into separate `mode`, `output`, and `connection` settings with mode-implied defaults and explicit overrides.
- Added interactive controls while a request is running:
  - `s` stops waiting and returns to the prompt
  - `q` quits immediately
- Added `--self-test` to verify API key presence, connectivity, model access, and response generation.
- Replaced the hanging OpenAI SDK `responses.create(...)` flow with direct `httpx` calls to `POST /v1/responses`.
- Added app-level timeout handling around LLM requests.
- Improved waiting output:
  - friendly output shows a compact inline `waiting...`
  - verbose output shows per-second labeled wait logs
- Added `scripts/smoke_test.py` for a minimal end-to-end smoke check of calculator behavior, math fallback, and basic LLM response.
- Fixed wait-thread shutdown so progress output is stopped and joined cleanly before process exit.
- Centralized debug printing through a small helper and added timing output for timed request paths in debug mode.
- Expanded smoke coverage with one additional stable natural-language calculator case.
- Added concise completion summaries after timed LLM calls, including elapsed time in all modes and token usage when the API provides it.
- Added an optional `--verbose` mode to `scripts/smoke_test.py` while keeping default smoke output compact.
- Added lightweight shared logging to `logs/latest.log` for each run, with optional extra append logging via `--log-file`.
- Normal-mode `waiting...` now finalizes into a concise completion or failure line instead of leaving partial wait artifacts behind.
- Friendly output now keeps completion summaries minimal, while model and token details remain in verbose/debug output.
- Friendly output now clears successful wait lines without printing a completion summary before the answer.
- Verbose/debug calculator failure logs were shortened to avoid repeating the exact same error line twice.
- Verbose/debug LLM status lines now use a simplified `LLM:<model>` label and avoid redundant post-completion messages.
- Verbose/debug LLM status labels now use bracketed formatting, and corrected-input logging is skipped when the text did not change.
- Verbose/debug wait lines now format as `[LLM:...] WAIT Ns` without double brackets.
- Tightened the LLM prompts to prefer one short sentence whenever possible.
- Updated `README.md` to document the new CLI behavior.
- Synced the docs with the current CLI structure and logging behavior.
- Self-test output now uses `[PASS]`/`[FAIL]` prefixes for readability and consistency with the smoke test.
- Friendly-mode wait cleanup now clears the inline wait indicator without leaving an extra blank line after successful LLM calls.
- Extracted OpenAI transport and response parsing into `llm_client.py` while keeping `agent.py` focused on orchestration.
- Added a public `generate_text(...)` boundary in `llm_client.py` and threaded a separate `provider` setting through the CLI/runtime without changing current OpenAI-backed behavior.
- Added Ollama transport inside `llm_client.py` with explicit `openai`, `ollama`, and `auto` provider behavior.
- Implemented `auto` as local-first with OpenAI fallback only on transport, timeout, provider-unavailable, or empty-output failure.
- Added normalized provider results that include `text`, `provider`, `model`, and `fallback_used`, plus fallback metadata for debugging.
- Added verbose provider-result logging so it is visible which provider was attempted first, why fallback happened, and which provider answered.
- Expanded smoke coverage for OpenAI-only, Ollama-when-available, and `auto` provider behavior.
- Tightened OpenAI prompt construction to reduce token usage with shorter stable system prompts, lower output caps, low reasoning effort, and compact JSON routing output.
- Expanded `--self-test` with provider-aware generation checks for `openai`, `ollama`, and `auto`.
- Relaxed aggressive output caps after GPT-5-nano self-tests showed that tiny visible answers can still require much larger total output-token budgets.
- Reduced redundant OpenAI self-test calls and allowed `auto` self-test to report `SKIP` on fallback rate limits instead of a misleading hard failure.

## Recent User Requests

- Add minimal comments only where intent is non-obvious.
- Add command-line mode selection with `argparse`.
- Make LLM wait/debug behavior visible.
- Add timeouts and request interruption controls.
- Diagnose why LLM fallback was hanging.
- Add a stronger self-test that checks multiple layers.
- Update the README with the new workflow.
- Add this context file for future major updates.
- Reconstruct the latest checkpoint from repo docs and git state.
- Assess whether the current file structure should stay as-is or take a small refactor.
- Plan a small LLM-provider refactor so a local Ollama model can be tried first and OpenAI can remain the fallback.
- Use a branch for that provider refactor rather than changing the current checkpoint in place.
- Separate the LLM request layer from `agent.py` as the first small step toward multi-provider support.
- Add Ollama transport and explicit local-first fallback behavior while keeping `connection` and `provider` separate.

## Current Short-Term Goal

- Keep the CLI stable and easy to debug.
- Preserve the working direct-HTTP OpenAI path.
- Keep the runtime config model easy to reason about and re-test.
- Keep friendly output compact and clean.
- Make future sessions easier by keeping docs aligned with the code.
- Keep the new `llm_client.py` boundary stable and easy to reason about.
- Re-test the new Ollama and `auto` provider behavior in a real local environment.
- Avoid a broad redesign; keep the refactor small and centered on provider logic.

## Known Issues And Things To Verify

- Re-check `README.md` in the editor after the rewrite to confirm the encoding cleanup is fully resolved.
- The stop action is a soft cancel of the local wait. It does not guarantee the in-flight HTTP request is truly aborted server-side.
- The waiting indicator and threaded timeout flow should be re-tested after any future refactor touching CLI control flow.
- `--self-test` currently checks many layers and prints results directly; if the output format changes later, keep it readable in both friendly and verbose usage.
- Runtime behavior now depends on the interaction between `mode`, `output`, and `connection`; CLI resolution changes should be re-tested carefully.
- `agent.py` is still the highest-pressure file, but provider transport is now separated into `llm_client.py`.
- Ollama availability and local-first fallback behavior should be re-tested outside the sandbox because local model availability is environment-specific.

## What We Believe Is True Right Now

- API key, network reachability, authenticated model access, and direct `/v1/responses` calls are working.
- The earlier hanging issue was isolated to the SDK-based response call path in this environment.
- The current direct `httpx` implementation is the preferred request path for this repo.
- The latest uncommitted checkpoint adds the runtime config split, shared logging, and doc updates around that work.
- The smallest justified refactor was to separate provider transport from orchestration so multiple LLM backends can be supported cleanly.
- The provider layer now supports OpenAI, Ollama, and explicit `auto` fallback rules while keeping `connection` separate from `provider`.

## Suggested Next Steps

- Re-run a quick README sanity check in the editor after the rewrite.
- Re-run the smoke test and a couple of manual CLI combinations after the latest runtime-config changes.
- Decide whether to commit the current checkpoint.
- Re-run provider-specific manual checks for `--provider openai`, `--provider ollama`, and `--provider auto`.
- If provider behavior looks stable, commit this branch checkpoint before any further cleanup.
- If future work expands the agent, keep `docs/CONTEXT.md`, `docs/ROADMAP.md`, and `README.md` aligned.
