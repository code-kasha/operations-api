# Deployment

The Docker image runs Operations API in production mode: Gunicorn as an unprivileged user, PostgreSQL, HTTPS only, and static files (admin, Swagger UI, ReDoc) served by WhiteNoise. It refuses to start when its settings are unsafe. Tests and CI use SQLite by design; production needs PostgreSQL.

## The image

Each release publishes `ghcr.io/code-kasha/operations-api`, tagged with its version (for example `v1.0.0`) and `latest`, for amd64 and arm64. To build it from a clone instead:

```sh
docker build -t operations-api:local .
```

The examples below use `operations-api:local`; substitute the published name to skip the build.

The image's default command serves the app without migrating: migrations are a separate deployment step. The hosted demo is the exception (see [Hosted demo](#hosted-demo)). For a disposable local demo on SQLite, use `docker compose up --build -d` from the [README quick start](../README.md#quick-start) instead.

## Configuration

Copy `.env.example` to `.env` and replace every value. Python does not load `.env` automatically; pass it to Docker with `--env-file .env`.

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | Required. A unique random secret of at least 50 characters: `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`. |
| `ALLOWED_HOSTS` | Required. Comma-separated host names; `*` is refused. |
| `DATABASE_URL` | Required. A `postgresql://` URL; add `?sslmode=require` for Neon and most hosted databases. |
| `CSRF_TRUSTED_ORIGINS` | The site's HTTPS origin, e.g. `https://operations.example.com`, for the admin login. |
| `TRUST_PROXY_HTTPS` | `true` only behind a proxy that terminates HTTPS and overwrites `X-Forwarded-Proto`. Without it, every request redirects to HTTPS. |
| `ORGANISATION_NAME` | The installation's organisation name. |
| `ORGANISATION_SECTOR` | `office` (default) enables timesheets and overtime. `school` and `clinic` run the shared core only; their modules are not implemented. |
| `PORT` | Listening port, default `8000`; hosts such as Render set it. |
| `SITE_REVISION` | Optional. The commit being served, reported by `/health/`; Render's `RENDER_GIT_COMMIT` is used when it is unset. |
| `DEMO_UNTIL` | Hosted demo only: an ISO date such as `2026-12-27`. It shows the end date in the API description and `/health/`, and allows `reset_demo`. Leave it unset everywhere else. |
| `DEMO_PASSWORD` | Hosted demo only: the shared password for the fictional `demo.*` accounts. |

`DJANGO_SETTINGS_MODULE` is `config.settings.production` in the image. Production forces HTTPS redirects, secure cookies and HSTS for one year (with subdomains and preload), so enable it only on a domain that serves HTTPS.

## Deploying it yourself

Run PostgreSQL, the image, and an HTTPS reverse proxy that sets `X-Forwarded-Proto` (Caddy, nginx or your platform's load balancer). Then:

```sh
docker run --rm --env-file .env operations-api:local python manage.py check --deploy
docker run --rm --env-file .env operations-api:local python manage.py migrate --noinput
docker run --rm -it --env-file .env operations-api:local python manage.py createsuperuser
docker run -d --name operations-api --restart unless-stopped --env-file .env -p 127.0.0.1:8000:8000 operations-api:local
```

Point the proxy at `127.0.0.1:8000`. Check `https://your-domain/health/`: it reports `ok`, the version and the revision, or `unavailable` with status 503 if the database cannot be reached. It does not check that migrations have run.

To load fictional data into an empty database, run `python manage.py load_sample_data --password '…'` the same way. It refuses databases that already have employees.

**Operations.**

- Run `python manage.py flushexpiredtokens` daily, to remove expired refresh tokens.
- Back up PostgreSQL before every update, because migrations only move forward.
- To update, pull or build the new image, run `migrate`, then replace the container.
- To roll back, restore the backup and start the previous image tag.
- Login endpoints have a 30 requests/minute throttle per process. Across several workers, put rate limiting in the proxy.

**Verified** on 27 September 2026 with Docker Engine 29.8.0 and PostgreSQL 17.11 in containers, using `TRUST_PROXY_HTTPS=true` and an `X-Forwarded-Proto: https` header in place of a real proxy. The following all passed:

- `check --deploy` with no warnings, the migrations, and `load_sample_data`
- plain HTTP redirecting to HTTPS (301), HSTS, `/health/`, JWT login and the payroll register
- static files, Swagger UI, unknown hosts refused (400), and the non-root user
- `reset_demo` refusing to run without `DEMO_UNTIL`
- the full test suite (345 tests) run once against PostgreSQL. CI keeps SQLite.
- the arm64 image building and passing `check` under emulation

Not verified: a real domain, certificate and proxy, and PostgreSQL concurrency under load.

**Support window.** Django 5.2 LTS receives security fixes until April 2028. Upgrade Django before running a fork publicly after that.

## Hosted demo

The public demo, [operations-api-ji51.onrender.com](https://operations-api-ji51.onrender.com/), runs the image on [Render](https://render.com/)'s free tier with a free [Neon](https://neon.tech/) PostgreSQL 17 database in Singapore, until **27 December 2026**. After that date it shuts down as planned; run it yourself with the [quick start](../README.md#quick-start).

The demo's accounts and shared password are public, so anyone can change its data. The demo therefore starts with `deploy/demo-start.sh`, which migrates, **erases every record and loads fresh sample data** with `reset_demo`, then serves. Render's free services sleep after 15 minutes without traffic, so the demo resets whenever it wakes, and its dates stay current. The first request after a quiet spell takes about a minute.

`reset_demo` refuses to run unless `DEMO_UNTIL` is set. Never set `DEMO_UNTIL` on a database whose data matters.

To set it up (for a fork, for example):

1. Create a Neon project with PostgreSQL 17 and copy its connection string. It includes `sslmode=require`.
2. On Render, create a **Web Service** from the GitHub repository, branch `main`. Render detects the `Dockerfile`; choose the **Free** instance type.
3. Set the **Docker Command** to `sh deploy/demo-start.sh`, the health check path to `/health/`, and turn **Auto-Deploy** off so only CI deploys.
4. Set the environment variables, using the service's `onrender.com` host name:
   - `SECRET_KEY`: a new random secret
   - `ALLOWED_HOSTS=your-service.onrender.com`
   - `CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com`
   - `DATABASE_URL`: the Neon connection string
   - `DEMO_UNTIL=2026-12-27`
   - `DEMO_PASSWORD`: the password to publish in the README
   - `TRUST_PROXY_HTTPS=true`, because production redirects plain HTTP to HTTPS (see below)
5. Copy the service's **Deploy Hook** URL. In the GitHub repository's **Settings → Secrets and variables → Actions**, add it as the secret `DEPLOY_HOOK_URL`. Add `DEMO_URL` (the service's `https://…onrender.com` address) as a repository variable, a `production` environment variable, or a secret. Until both are set, the `deploy` job only notes that there is no demo to deploy.

After every push to `main`, the `deploy` job in CI waits for the checks, triggers the deploy hook, and waits until `/health/` reports the new commit. It appears as the `production` environment under the repository's Deployments.

Render terminates HTTPS in front of the app and forwards plain HTTP with `X-Forwarded-Proto`. Without `TRUST_PROXY_HTTPS=true`, Django would see HTTP and redirect in a loop. Trusting the header is safe only if every request reaching the app arrived over HTTPS. Render redirects plain HTTP to HTTPS at its edge, which makes that true. Confirm it when deploying: `curl -I http://your-service.onrender.com/health/` should be redirected by Render, and `https://` should return 200.

**Verified on Render and Neon** on 27 September 2026:
- Render's edge redirects plain HTTP to HTTPS (301), and HSTS is set.
- The start script migrates, resets the data and serves.
- JWT login works; a wrong password returns 401.
- The payroll register matches the local run, and role scoping holds (a manager sees their department; an employee gets 404 on the register and 403 on headcount).
- The CI deploy job waits until `/health/` reports the pushed commit.

Two setup mistakes produce misleading symptoms:
- An `ALLOWED_HOSTS` value that doesn't exactly match the host name returns 400 for every request, including `/health/`; the logs name the refused host.
- Omitting the Docker Command leaves the database unmigrated: `/health/` still passes, but login returns 500.

## CI and releases

GitHub Actions runs on every push and pull request. It installs the frozen lockfile, then:

- checks formatting and lint
- runs the tests on SQLite
- checks for missing migrations and a stale `schema.yml`
- builds the image and smoke-tests it

Pushing a `v*` tag makes a release, in order, and only if each step succeeds:

1. **The checks** above.
2. **The image.** The tag must match the version in `pyproject.toml`. The image is built for amd64 and arm64 and pushed to `ghcr.io/<owner>/<repository>` as the tag and as `latest`, with OCI labels for its source, license, version and revision.
3. **The GitHub Release.** Its notes are the tag's `CHANGELOG.md` entry. It carries the OpenAPI schema (`operations-api-vX.Y.Z-openapi.yml`) and `SHA256SUMS`.

To release, set the version in `pyproject.toml`, give the `CHANGELOG.md` entry a `## X.Y.Z (date)` heading, and push the tag, for example `git tag v1.0.1 && git push origin v1.0.1`. A new package on GitHub's registry starts private; make it public under the package's settings.
