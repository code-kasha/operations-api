# Operations API

A Django REST API foundation for staff operations in schools, clinics, and small businesses. Each installation serves one organisation. This public project is built from scratch with fictional data; the real client code is private.

[API reference](docs/api.md) · [Deployment](docs/deployment.md) · [Contributing](CONTRIBUTING.md) · [MIT licence](LICENSE)

**Status: initial setup, under development.** No release or hosted demo exists yet.

Available now:

- JWT login, rotating refresh tokens, logout by refresh-token blacklisting, and current-user endpoint.
- Custom user model and Django admin.
- Swagger UI, ReDoc, and a committed OpenAPI schema.
- Database health endpoint, SQLite development/tests, PostgreSQL production settings.
- Locked uv environment, Docker image definition, and GitHub Actions checks.

Planned for v1.0.0: employees, departments, business roles, attendance, leave, payroll, reports, fictional sample data, and the office module (timesheets, overtime, approvals). Schools and clinics follow later. These features are not implemented. Payroll does not currently calculate salaries or provide statutory compliance (including PF, ESI, or TDS). The clinic module will cover staff only, with no patient or medical records. See the [implementation plan](docs/roadmap.md).

## Quick start

From this folder, with Docker Desktop running:

```sh
docker compose up --build -d
```

This starts a disposable local SQLite demo in development mode. Remove it with `docker compose down`; the database is lost when the container is removed. To create an admin account while it is running:

```sh
docker compose exec api python manage.py createsuperuser
```

With Python 3.13 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

The Python path keeps data in the ignored `db.sqlite3` file. No credentials are bundled.

Open [Swagger UI](http://127.0.0.1:8000/api/docs/), [ReDoc](http://127.0.0.1:8000/api/redoc/), or [admin](http://127.0.0.1:8000/admin/). Check [health](http://127.0.0.1:8000/health/).

## Development

```sh
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run pytest
uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml
git diff --exit-code -- schema.yml
```

CI runs these checks on SQLite and builds/smoke-tests the Docker image. A local test pass does not imply that hosted CI has run.

## Layout and conventions

- `apps/accounts/`: authentication identity, admin, and current-user endpoint.
- `config/settings/`: shared, development, test, and production settings.
- `tests/`: authentication behavior, health/docs, and production configuration guards.
- `schema.yml`: generated API contract.
- `docs/`: API, deployment, and architectural boundaries.

Business modules will follow `View → Serializer → Service → Database`: validation at the boundary, transactional writes in services, and role-filtered querysets that return 404 for hidden records. See [architecture](docs/architecture.md) for decisions and remaining work.
