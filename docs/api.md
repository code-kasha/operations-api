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

Attendance, payroll, reporting, and sector endpoints remain planned.
