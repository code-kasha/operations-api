# Contributing

Read [agent-start.md](agent-start.md) and [architecture](docs/architecture.md) before changing scope. Use fictional data only.

Run `uv sync --frozen`, migrate, and use the checks in [README.md](README.md#development). Include meaningful behavioral tests for authentication, permissions, transactions, or business rules that change. Generate migrations for model changes and regenerate `schema.yml` when the API changes. CI intentionally uses SQLite.

Commit locally. Do not push, open PRs, publish, or deploy without Akash's explicit request. End agent-assisted commit messages with `Assisted-by: OpenAI Codex` and a `Co-Authored-By:` line for Claude.
