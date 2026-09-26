# Project instructions

Read `docs/architecture.md` and `docs/roadmap.md` before working on this project. Maintainer notes, when present locally, live outside the repository in `../operations-api-notes/`.

- One organisation per install; API only; fictional data only.
- Tests and CI use SQLite. Production uses PostgreSQL.
- Follow the service-layer and role-filtered queryset conventions documented in `docs/architecture.md` as business modules are introduced.
- Keep README claims limited to implemented, easily verified behavior.
- First release is core + offices, as selected by Akash. Follow `docs/roadmap.md`;
  ask before changing this scope or assigning later sector releases.
- Commit locally; never push or open a PR without an explicit request in that message.
- End agent-assisted commit messages with both `Assisted-by: OpenAI Codex` and the
  `Co-Authored-By:` line for Claude from the session instructions.
- Follow the check commands in `README.md`; keep migrations and `schema.yml` current.
