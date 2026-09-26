# Implementation plan

Akash selected **shared core + offices** for the first release, targeting v1.0.0.
The foundation, staff/permissions, attendance/leave, office operations, basic payroll, and reports/sample data are implemented. The remaining steps
record intended work, not shipped capabilities or a delivery-date commitment.

## Build order

1. **Staff and permissions — implemented.** Departments, employee records linked to user
   accounts, business roles, and role-scoped access. The permission
   matrix is documented in [permissions](permissions.md). Tests cover visibility,
   forbidden writes, privilege escalation, and hidden-record 404s. Business roles
   remain distinct from Django admin access; changes are audited in transactions.
2. **Attendance and leave — implemented.** Shifts, dated assignments,
   check-in/check-out, holidays, and leave review/cancellation. Time-zone,
   overlap, absence, and working-day rules are in [attendance](attendance.md),
   with tests for visibility, transitions, boundaries, and rollback.
3. **Office operations — implemented.** Timesheet drafts and task entries,
   submission/review, and separate overtime requests. Tests cover ownership,
   approvals, duplicate/overlapping time, and immutable approved work. The
   [office rules](offices.md) document the input and no-double-counting contract
   that payroll follows.
4. **Payroll — implemented.** Salary structures, monthly pay runs, and payslips
   with working-day pro-rating (selected by Akash). Overtime is a multiplier or
   flat rate per structure, since the policy is still undecided. Rounding and
   overtime rules are in [payroll](payroll.md). Tests cover calculations,
   rollback, duplicate runs, and locked immutability. Gross pay only; no
   statutory claims. Fuller-version ideas are in
   [payroll improvements](payroll-improvements.md).
5. **Reports and sample data — implemented.** Monthly attendance summary,
   payroll register, and headcount with role-scoped access, and an atomic,
   repeatable `load_sample_data` command covering the office workflow through
   a locked pay run. See [reports](reports.md).
6. **Release preparation.** Complete the API/deployment guides, committed
   schema, behavioral tests, and CI checks. Verify Docker startup and
   PostgreSQL deployment configuration. Prepare the multi-architecture
   image workflow, release notes/checksums, demo end date, and README
   screenshots based on working features. Publishing and deployment need
   an explicit request.

Each implementation step includes migrations where needed, service-layer
writes, permission checks, tests, and updated API documentation/schema.
Tests and CI continue to use SQLite.

## First-release completion criteria

A reviewer can load fictional office data and follow an employee through
attendance, leave, timesheet/overtime approval, monthly payroll, and reports
using Swagger UI or the admin. Permissions prevent access to hidden staff
and payroll records. Finished pay runs cannot be changed. The documented
quick starts work, and README claims match observable behavior.

## Later sectors

Schools add teaching subjects, timetables, and cover for absent teachers.
Clinics add duty rosters, on-call rotas, and minimum staffing per shift,
without patient records. Their release order and versions remain undecided.
