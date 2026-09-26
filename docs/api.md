# API reference

The generated contract is [schema.yml](../schema.yml). Interactive docs are at `/api/docs/` and `/api/redoc/`; raw schema is at `/api/schema/`.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health/` | Public database probe; 200 with `{"status":"ok"}`, or 503 with `{"status":"unavailable"}`. |
| POST | `/api/v1/auth/token/` | Exchange `username` and `password` for `access` and `refresh`. |
| POST | `/api/v1/auth/token/refresh/` | Exchange `refresh` for a new token pair; old refresh is blacklisted. |
| POST | `/api/v1/auth/logout/` | Blacklist the supplied `refresh`; returns 200. |
| GET | `/api/v1/auth/me/` | Return the authenticated user's public account fields. |

Create a user with `createsuperuser` or through the admin. There is no public registration. Send JSON request bodies. Authenticate protected requests with `Authorization: Bearer <access>`; in Swagger's Authorize dialog, paste the access token.

Access tokens last five minutes; refresh tokens last one day. Logout revokes only the submitted refresh token, and existing access tokens remain valid until expiry. Refresh rotation follows the [Simple JWT settings](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html). Token operations share a 30 requests/minute IP throttle using Django's local cache; production needs proxy rate limiting for enforcement across workers.

## Staff API

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/api/v1/departments/` | List visible departments or create one. |
| GET, PUT, PATCH, DELETE | `/api/v1/departments/{id}/` | Read/update a visible department; delete only when unused. |
| GET, POST | `/api/v1/employees/` | List visible employees or create one linked to an existing user. |
| GET, PUT, PATCH | `/api/v1/employees/{id}/` | Read/update an employee; no deletion. |
| POST | `/api/v1/employees/{id}/role/` | Assign a business role with `{"role":"hr"}` (admin only). |
| GET | `/api/v1/staff-activity/` | Paginated activity list, visible only to admin/HR. |
| GET | `/api/v1/staff-activity/{id}/` | Read a visible activity entry. |

Lists use page-number pagination (`?page=2`), with 25 records per page. See the
[permission matrix](permissions.md) for visibility and write rules. Role and account
fields cannot be changed through employee updates; attempts are rejected with 400.
Unknown and read-only input fields are rejected. Invalid employment dates, duplicate
employee numbers/account links, and referenced-department deletion return 400.

### Staff onboarding

1. Create a superuser using the quick start, then log into Django admin.
2. Create a normal user account there, leaving staff/superuser privileges disabled.
   Note its numeric ID from the admin change-page URL.
3. In Swagger, use the superuser's credentials at `/api/v1/auth/token/` and authorize
   with the returned access token.
4. POST a department: `{"code":"operations","name":"Fictional Operations"}`.
5. POST an employee, substituting the actual user and department IDs:

```json
{
  "user": 2,
  "department": 1,
  "employee_number": "DEMO-001",
  "first_name": "Fictional",
  "last_name": "Coordinator",
  "job_title": "Office Coordinator",
  "start_date": "2026-09-01"
}
```

6. POST `{"role":"admin"}` to that employee's `/role/` endpoint. Sign in as the
   ordinary account to manage operations with its new business role. The account
   does not receive Django admin privileges.

Use PATCH `{"is_active":false}` to deactivate other employees. Operational access
is revoked immediately; login is independent. To disable login too, deactivate the
authentication account in Django admin. There is no fictional-data seed command yet.

## Attendance and leave API

See [attendance rules](attendance.md) for permissions, time boundaries, day
classification, and transitions. All lists are paginated.

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/api/v1/shifts/` | Read templates; admin/HR create shifts. |
| GET, PUT, PATCH, DELETE | `/api/v1/shifts/{id}/` | Read; admin/HR change/delete only while unassigned. |
| GET, POST | `/api/v1/shift-assignments/` | Read visible schedules; admin/HR assign future shifts. |
| GET, DELETE | `/api/v1/shift-assignments/{id}/` | Read with `day_status`; admin/HR remove eligible future assignments. |
| GET, POST | `/api/v1/holidays/` | Read calendar; admin/HR declare future holidays. |
| GET, DELETE | `/api/v1/holidays/{id}/` | Read; admin/HR remove future holidays. |
| GET | `/api/v1/attendance/` and `/api/v1/attendance/{id}/` | Read visible attendance. |
| POST | `/api/v1/attendance/check-in/` | Supply `{"assignment":1}` for your shift; returns 201. |
| POST | `/api/v1/attendance/{id}/check-out/` | Submit `{}`; close your attendance with server time. |
| GET, POST | `/api/v1/leave-requests/` | Read visible requests; submit your own. |
| GET | `/api/v1/leave-requests/{id}/` | Read request, working dates, and review/cancellation metadata. |
| POST | `/api/v1/leave-requests/{id}/review/` | Reviewer supplies `decision` (`approved`/`rejected`) and optional `note`. |
| POST | `/api/v1/leave-requests/{id}/cancel/` | Submit `{}` to withdraw/cancel when permitted. |

Create a shift with `{"name":"Fictional office day","start_time":"09:00","end_time":"17:00"}`.
Assign it with `{"employee":1,"shift":1,"date":"2026-10-05"}`, replacing the IDs
and using a future date. Scheduling must precede leave submission:

```json
{
  "start_date": "2026-10-05",
  "end_date": "2026-10-06",
  "leave_type": "paid",
  "reason": "Fictional personal leave"
}
```

Replace dates with future scheduled dates. Employees cannot supply status,
employee ID, reviewer, or timestamps. Illegal transitions, overlaps, and schedule
conflicts return 400; forbidden operations on visible records return 403.

## Office API

These endpoints require `ORGANISATION_SECTOR=office`. Read the
[office rules](offices.md) for permissions, transitions, and payroll boundaries.
Timesheet/overtime lists use the standard pagination. Entries are embedded in
their parent timesheet; there is no separate entry list endpoint.

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/api/v1/offices/timesheets/` | Read visible sheets; create your draft using `{"attendance":1}`. |
| GET | `/api/v1/offices/timesheets/{id}/` | Read entries, totals, status, and reviewer metadata. |
| POST | `/api/v1/offices/timesheets/{id}/entries/` | Owner adds a task interval to a draft. |
| GET, PUT, PATCH, DELETE | `/api/v1/offices/timesheet-entries/{id}/` | Read; owner edits/deletes only while parent is a draft. |
| POST | `/api/v1/offices/timesheets/{id}/submit/` | Owner submits using `{}`. |
| POST | `/api/v1/offices/timesheets/{id}/review/` | Reviewer sends `decision` (`approved`/`rejected`) and optional `note`. |
| POST | `/api/v1/offices/timesheets/{id}/cancel/` | Owner cancels draft/submitted work using `{}`. |
| GET, POST | `/api/v1/offices/overtime-requests/` | Read visible claims; request overtime from your approved sheet. |
| GET | `/api/v1/offices/overtime-requests/{id}/` | Read claim, duration, status, and review metadata. |
| POST | `/api/v1/offices/overtime-requests/{id}/review/` | Reviewer sends `decision` and optional `note`. |
| POST | `/api/v1/offices/overtime-requests/{id}/cancel/` | Owner withdraws a pending claim using `{}`. |

After checking out, create a timesheet and add entries using actual recorded
bounds. The following is an illustrative payload, not seeded data:

```json
{
  "description": "Fictional month-end reconciliation",
  "starts_at": "2026-10-05T09:01:00+05:30",
  "ends_at": "2026-10-05T19:00:00+05:30"
}
```

Submit, then have a different eligible user approve the sheet. If the scheduled
shift ended at 17:00 and approved entries cover the interval, request overtime:

```json
{
  "timesheet": 1,
  "starts_at": "2026-10-05T17:00:00+05:30",
  "ends_at": "2026-10-05T19:00:00+05:30",
  "reason": "Fictional month-end deadline"
}
```

Replace IDs and dates with your own completed records. Review the overtime
request separately; approving a timesheet alone does not approve extra pay.

## Payroll API

Read the [payroll rules](payroll.md) for calculations, rounding, and access. Admin/HR
manage payroll; employees read their own structures and locked payslips.

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/api/v1/payroll/salary-structures/` | Read visible structures (`?employee=`); admin/HR create one. |
| GET, DELETE | `/api/v1/payroll/salary-structures/{id}/` | Read; delete only when no payslip uses it. |
| GET, POST | `/api/v1/payroll/pay-runs/` | Admin/HR list runs or create one with `{"year":2026,"month":10}`. |
| GET, DELETE | `/api/v1/payroll/pay-runs/{id}/` | Read; delete a draft run. |
| POST | `/api/v1/payroll/pay-runs/{id}/recalculate/` | Recalculate a draft using `{}`. |
| POST | `/api/v1/payroll/pay-runs/{id}/lock/` | Lock a draft using `{}`; locked runs are final. |
| GET | `/api/v1/payroll/payslips/` and `/{id}/` | Read visible payslips (`?pay_run=`, `?employee=`). |

Create a structure with multiplier overtime:

```json
{
  "employee": 1,
  "effective_from": "2026-09-01",
  "monthly_base": "42000.00",
  "overtime_method": "multiplier",
  "overtime_multiplier": "1.50"
}
```

For a flat rate, send `"overtime_method": "flat"` and `"overtime_hourly_rate": "300.00"`
instead of the multiplier. Money is returned as decimal strings.

Reporting, schools, and clinics remain planned.
