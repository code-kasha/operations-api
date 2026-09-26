# Changelog

## Unreleased

Prepared as v1.0.0, the first and final planned release: the shared core plus the office module. Operations API is complete as of this version and not actively maintained; fork it freely. At tagging, this heading becomes `## 1.0.0 (date)`.

- **Staff and roles:** departments, employee records linked to user accounts, and operations admin, HR, manager and employee roles. Visibility is scoped by role, and hidden records return 404. HR cannot edit admins, and nobody changes their own role. Every change is recorded in an activity log.
- **Attendance and leave:** shift templates, dated assignments (including overnight shifts), holidays, and server-timed check-in and check-out. Paid and unpaid whole-day leave, with scoped reviews, cancellation, and no self-approval.
- **Office work:** timesheets with non-overlapping task intervals, submission and review, and separately approved overtime that must be covered by recorded work. Approved work is immutable.
- **Payroll:** immutable salary structures, each choosing multiplier or flat-rate overtime. Monthly pay runs pro-rate base pay by standard working days (weekdays minus holidays) for joiners, leavers, absences and unpaid leave, and round half-up to the paisa. Approved overtime is paid exactly once. Draft runs can be recalculated; locked runs never change. Employees see only their own locked payslips. Gross pay only: no deductions or statutory rules.
- **Reports:** monthly attendance summary, payroll register and headcount, each scoped by role.
- **Sample data:** `load_sample_data` loads a fictional office with a month of history and a locked pay run, atomically; repeating it changes nothing.
- **API:** JWT authentication with rotating, blacklisted refresh tokens, and Swagger UI, ReDoc and a committed OpenAPI schema with endpoints grouped by resource. `/health/` reports status, version and the commit served.
- **Deployment:** production settings that refuse unsafe configuration, a Docker image (amd64 and arm64) running as an unprivileged user, and PostgreSQL in production; verified against PostgreSQL 17. A hosted-demo mode where `reset_demo` restores fresh sample data on every start, and refuses to run anywhere else.
- **CI and releases:** lint, formatting, tests on SQLite, missing-migration and stale-schema checks, and a Docker build with a smoke test. Tags publish the image to GHCR and a GitHub Release with the OpenAPI schema and `SHA256SUMS`.

Release assets: the OpenAPI schema and `SHA256SUMS`. Container image: `ghcr.io/code-kasha/operations-api:v1.0.0` (also `latest`).
