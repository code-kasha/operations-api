# Changelog

## Unreleased

- Add departments, employee records, operations admin/HR/manager/employee roles, and scoped visibility.
- Add transactional staff services, immutable account links, employment-date constraints, and activity auditing.
- Restrict role assignment to operations admins and protect privileged records from HR changes.
- Document staff onboarding and permissions; expose staff records read-only in Django admin.

- Initialize the Django API foundation, uv environment, custom authentication user, JWT routes, admin, health probe, and API documentation.
- Add split settings, production configuration guards, Docker local setup, SQLite tests, and CI checks.
- Record architecture and the selected first-release scope: shared core + offices.
