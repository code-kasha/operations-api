# Changelog

## Unreleased

- Add monthly attendance summary, payroll register, and headcount reports with role-scoped access.
- Add `load_sample_data`: a fictional office with a locked pay run, loaded atomically and safe to repeat.
- Share attendance day classification between the assignment API, payroll, and reports.

- Add immutable salary structures with a per-employee overtime method: multiplier of a derived hourly rate, or flat hourly rate.
- Add monthly pay runs with working-day pro-rating for joiners, leavers, absences, and unpaid leave; paise rounding; and draft recalculation.
- Pay approved office overtime once, with source links; lock finished runs; show employees only their own locked payslips.
- Document payroll rules, limits, and ideas for a fuller version.

- Add office timesheet drafts, recorded task intervals, submission, review, and withdrawal.
- Add separate overtime approval with recorded-work coverage and overlap checks; approved work is immutable.
- Enforce office-sector access, reuse scoped reviewer permissions, and document approved overtime as a future payroll input.

- Add shift templates, dated assignments, holidays, and self-service check-in/check-out.
- Add paid/unpaid whole-day leave, scoped review and cancellation, and self-approval protection.
- Preserve schedule snapshots and audit mutations atomically; classify assigned days for later reporting/payroll.

- Add departments, employee records, operations admin/HR/manager/employee roles, and scoped visibility.
- Add transactional staff services, immutable account links, employment-date constraints, and activity auditing.
- Restrict role assignment to operations admins and protect privileged records from HR changes.
- Document staff onboarding and permissions; expose staff records read-only in Django admin.

- Initialize the Django API foundation, uv environment, custom authentication user, JWT routes, admin, health probe, and API documentation.
- Add split settings, production configuration guards, Docker local setup, SQLite tests, and CI checks.
- Record architecture and the selected first-release scope: shared core + offices.
