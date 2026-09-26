# Architecture and boundaries

## Decisions

- API only; Swagger UI, ReDoc, and Django admin provide the interface.
- One organisation per deployment, configured with a sector; no multi-tenancy.
- Python 3.13, Django 5.2, DRF, uv, Ruff, and pytest.
- SQLite for local development and CI; PostgreSQL for production.
- A custom `accounts.User` exists before the first migration so employee and role models can evolve without replacing Django's auth table later.
- JWT authentication is implemented; business role permissions are not yet implemented. Django's admin permissions are separate from the planned operations roles.
- Development is the management-command default; WSGI/ASGI and the container default to production.

## Implementation conventions for upcoming modules

Keep views thin. Serializers validate request shape; services perform business mutations in transactions. Role-aware querysets control visibility, with hidden records returning 404. Write activity history only through the service responsible for the associated mutation. Payroll calculations and pay-run locking must be transactionally tested before being advertised.

## Planned scope, without release assignments

Shared core: staff/departments/roles; shifts/attendance/leave/holidays; salary structures/pay runs/payslips; attendance/payroll/headcount reports; permissions and an atomic fictional-data command.

Sector modules: schools (subjects/timetables/cover), clinics (rosters/on-call/minimum staffing), offices (timesheets/overtime/approvals).

Ask Akash whether the first release includes all sectors or one sector before making a release plan. The paid CRM remains a separate product. No patient records, real client data, or untested payroll compliance claims belong here.

At shipping time, list the portfolio, profile README, and GitHub social-preview updates from `agent-start.md`; do not edit those repositories without a request.
