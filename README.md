# Operations API

A Django REST API foundation for staff operations in schools, clinics, and small businesses. Each installation serves one organisation. This public project is built from scratch with fictional data; the real client code is private.

[API reference](docs/api.md) · [Deployment](docs/deployment.md) · [Contributing](CONTRIBUTING.md) · [MIT licence](LICENSE)

**Status: staff, attendance, leave, office operations, basic payroll, and reports implemented; under development.** No release or hosted demo exists yet.

Available now:

- JWT login, rotating refresh tokens, logout by refresh-token blacklisting, and current-user endpoint.
- Custom user model and Django admin.
- Departments and employee records, with operations admin, HR, manager, and employee roles.
- Role-scoped visibility, transactional staff changes, and a read-only activity trail.
- Dated shifts (including overnight work), holidays, and server-timed check-in/check-out.
- Whole-day paid/unpaid leave, department-scoped reviews, and no self-approval.
- Office timesheet drafts, task intervals, submission/review, and separate overtime approvals.
- Monthly gross pay: salary structures, working-day pro-rating for absence and unpaid leave, multiplier or flat-rate overtime, and lockable pay runs.
- Monthly attendance summary, payroll register, and headcount reports, scoped by role.
- A repeatable command that loads a fictional office, including a locked pay run.
- Swagger UI, ReDoc, and a committed OpenAPI schema.
- Database health endpoint, SQLite development/tests, PostgreSQL production settings.
- Locked uv environment, Docker image definition, and GitHub Actions checks.

Still planned for v1.0.0: release preparation. Schools and clinics follow later and are not implemented. Payroll calculates gross pay only: no deductions, net pay, or statutory compliance (including PF, ESI, or TDS). The clinic module will cover staff only, with no patient or medical records. Read the [attendance rules](docs/attendance.md), [office rules](docs/offices.md), [payroll rules](docs/payroll.md), [reports and sample data](docs/reports.md), and [implementation plan](docs/roadmap.md).

## Quick start

From this folder, with Docker Desktop running:

```sh
docker compose up --build -d
```

This starts a disposable local SQLite demo in development mode. Remove it with `docker compose down`; the database is lost when the container is removed. To create an admin account while it is running:

```sh
docker compose exec api python manage.py createsuperuser
```

To explore with fictional office data instead, load the demo accounts (all sharing the password you choose):

```sh
docker compose exec api python manage.py load_sample_data --password 'choose-a-strong-password'
```

With Python 3.13 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py load_sample_data --password 'choose-a-strong-password'  # optional
uv run python manage.py runserver
```

The Python path keeps data in the ignored `db.sqlite3` file. No credentials are bundled.

Open [Swagger UI](http://127.0.0.1:8000/api/docs/), [ReDoc](http://127.0.0.1:8000/api/redoc/), or [admin](http://127.0.0.1:8000/admin/). Check [health](http://127.0.0.1:8000/health/).

With sample data, log in through Swagger as `demo.hr`, `demo.manager`, or
`demo.employee`; see [sample data](docs/reports.md#fictional-sample-data).
Otherwise, use the superuser to create ordinary accounts in admin, then log in through
Swagger to create departments and employee records. Assign the first operations
admin through the employee role endpoint. See [onboarding](docs/api.md#staff-onboarding)
and the [permission matrix](docs/permissions.md). Business records are read-only
in Django admin; their changes go through the API.

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
- `apps/staff/`: departments, employees, business permissions, transactional services, and activity.
- `apps/attendance/`: shifts, dated assignments, holidays, clocking, and leave review services.
- `apps/offices/`: timesheets, task intervals, overtime requests, and approval services.
- `config/settings/`: shared, development, test, and production settings.
- `tests/`: authentication behavior, health/docs, and production configuration guards.
- `schema.yml`: generated API contract.
- `docs/`: API, deployment, and architectural boundaries.

Staff writes follow `View → Serializer → Service → Database`: validation at the boundary, transactional writes in services, and role-filtered querysets that return 404 for hidden records. See [architecture](docs/architecture.md) for decisions and remaining work.
