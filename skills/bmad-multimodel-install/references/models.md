# Models to propose

These are the model ids and effort values each agent advertised to acpx 0.22.0, checked on 2026-11-19, plus what was learned from using them as reviewers.

The lists change as vendors ship models. When a definition names an id the agent no longer offers, the run fails and lists the valid ids, so a stale id never runs silently on another model.

## Antigravity (`run-agent: antigravity`)

- **Models:**
  - `gemini-4-hydrogen`
  - `gemini-4-argon`
  - `gemini-4-neon` (the default)
  - `gemini-3.8-flash`
  - `gemini-pro-orchestrator-neon`
  - `gemini-pro-orchestrator-g1-pro`
  - `claude-opus-5-5`
  - `claude-sonnet-5-5`
  - `gpt-oss-120b-medium`
- **Effort:** `low`, `medium`, `high`, `xhigh`.
- **Use as a reviewer:**
  - **Propose `gemini-4-hydrogen` with `high`.** As a second reviewer it found real issues the host's reviewers missed, with few false positives, in a few minutes per review.
  - **`gemini-4-argon` with `high`** went deeper into existing code but took about 19 minutes per review. Propose it only when the user values depth over time.
  - **Avoid `gemini-3.8-flash`** for reviews: it reported a false positive.
  - **Avoid `gpt-oss-120b-medium`**: it failed the review task.

## Claude (`run-agent: claude`)

- **Models:** `opus` (the default), `sonnet`, `haiku`, `fable`, and full ids such as `claude-fable-5-2`.
- **Effort:** `low`, `medium`, `high`, `xhigh`, `max`.
- **As a second opinion when the host is not Claude:** propose `opus` with `high`.

## Codex, Gemini CLI, OpenCode

Not checked yet. Propose leaving `model` and `effort` out, so the agent uses its own default, unless the user names a model. Say that this is unchecked.

## Why a second opinion from another vendor

A strong reviewer from another vendor next to the host's own reviewer caught more planted errors than two reviewers from the same vendor: 56.7% against 42.7%. A weak reviewer from another vendor added nothing (Song, arXiv 2610.01471, October 2026). So always propose a strong model for the extra opinion.
