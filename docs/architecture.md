# Architecture and boundaries

## Decisions

- API only; Swagger UI, ReDoc, and Django admin provide the interface.
- One organisation per deployment, configured with a sector; no multi-tenancy.
- Python 3.13, Django 5.2, DRF, uv, Ruff, and pytest.
- SQLite for local development and CI; PostgreSQL for production.
- A custom `accounts.User` exists before the first migration so employee and role models can evolve without replacing Django's auth table later.
- JWT authentication and employee-based business roles are implemented. Django's admin permissions are separate from operations roles; superusers can bootstrap an operations admin. See [permissions](permissions.md).
- Development is the management-command default; WSGI/ASGI and the container default to production.

## Implementation conventions

Keep views thin. Serializers validate request shape; services perform business mutations in transactions. Role-aware querysets control visibility, with hidden records returning 404. Write activity history only through the service responsible for the associated mutation. Payroll calculations and pay-run locking must be transactionally tested before being advertised.

`apps/staff` implements departments, employee/account links, fixed business roles,
and staff activity. Services recheck write permissions and lock existing target
rows during updates. Employee deletion is disabled and department/account foreign
keys are protected. Activity stores the actor, action, target, timestamp, and names
of submitted fields; it is not a before/after data snapshot. Staff admin views are
read-only to keep business mutations inside the service layer. SQLite tests verify
validation and rollback; they do not demonstrate PostgreSQL row-lock concurrency.

## Planned scope

`apps/attendance` implements the single-installation calendar, dated shift
snapshots, attendance, and leave. Its calendar lock serializes writes and related
employment-date changes; see [attendance](attendance.md) for the consistency model
and business rules. Audit events reuse the staff activity stream.

Shared core: staff/departments/roles; shifts/attendance/leave/holidays; salary structures/pay runs/payslips; attendance/payroll/headcount reports; permissions and an atomic fictional-data command.

Sector modules: schools (subjects/timetables/cover), clinics (rosters/on-call/minimum staffing), offices (timesheets/overtime/approvals).

Akash selected shared core + offices for v1.0.0. Schools and clinics follow later; their order and versions remain undecided. See [roadmap](roadmap.md) for implementation order and completion criteria. The paid CRM remains a separate product. No patient records, real client data, or untested payroll compliance claims belong here.

At shipping time, list the portfolio, profile README, and GitHub social-preview updates from `agent-start.md`; do not edit those repositories without a request.
