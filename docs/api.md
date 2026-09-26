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

There are no staff, attendance, payroll, reporting, or sector endpoints yet.
