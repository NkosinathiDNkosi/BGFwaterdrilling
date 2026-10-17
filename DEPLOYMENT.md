# Production deployment and operations

This Flask application is **host-independent**. Render is one option, not a runtime dependency. Any suitable Linux VM, container host, or Python web platform can run it with Python, a WSGI server, persistent database storage, and Redis-compatible rate-limit storage.

## 1. Required environment variables

Generate the two application secrets independently with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run it twice. Do not commit any generated value.

| Variable | Required value / purpose |
|---|---|
| `APP_ENV` | `production` |
| `FLASK_SECRET_KEY` | Random secret for public session and CSRF protection |
| `ADMIN_SECRET_KEY` | A different random secret for admin session and CSRF protection |
| `DATABASE_PATH` | Absolute path to a persistent SQLite file, e.g. `/var/lib/bwd/bwd_enquiries.db` on a Linux VM |
| `RATELIMIT_STORAGE_URI` | Private Redis-compatible URL shared across all app workers |
| `TRUST_PROXY_HEADERS` | Optional. Set to `true` only behind one known reverse proxy that overwrites forwarded headers |

Do not set `FLASK_DEBUG=1` in production. Secure cookies and HSTS are enabled when `APP_ENV=production`. The app refuses to start if required production secrets, storage path, or shared rate-limit backend are missing.

## 2. Install and run on a Linux host or container

Install Python 3.10+ and create a virtual environment. From the project directory:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Ensure the directory containing `DATABASE_PATH` exists and is writable by the application's service account. The app creates its schema and performs migrations at startup.

Start with Gunicorn:

```bash
gunicorn --workers 2 --bind 0.0.0.0:${PORT:-8000} app:app
```

Choose worker/process counts to suit the host. When using SQLite, keep the deployment to a single application instance with modest write volume. Gunicorn worker processes on the same host can share SQLite, but do not deploy multiple independent instances with separate local database files.

For a stable production service, configure the process manager or platform to restart Gunicorn after failures, terminate it gracefully, rotate logs, monitor disk usage, and run database backups. Restrict database and Redis network access to the application.

## 3. Admin account setup

Create the first administrator or deliberately rotate an existing account password with:

```bash
python manage_admin.py set-password admin
```

Replace `admin` with the intended username. Enter the new password when prompted. Run the command in the same environment and with the same `DATABASE_PATH` as the deployed app. Do not keep `ADMIN_PASSWORD` in production after one-time bootstrap. There is no bundled default account.

## 4. SQLite persistence and backups

SQLite is appropriate for a small, single-instance website. `DATABASE_PATH` must point outside temporary/build directories and to storage that survives application restarts. Create regular backups using a SQLite-aware backup approach; validate recovery by restoring a copy and checking the enquiry and admin tables.

When migrating an existing live site, back up the actual production DB first. Setting a new `DATABASE_PATH` does not copy old data automatically. Do not upload a database file or customer enquiry export into Git.

If multiple app instances, higher write concurrency, or managed point-in-time recovery is needed, use a managed PostgreSQL service and implement/test a PostgreSQL adapter for `database.py`. The current application database module is SQLite-specific; setting a PostgreSQL URL alone will not switch it to PostgreSQL.

## 5. Render as one hosting option

Render's filesystem is ephemeral unless you attach persistent storage. If using SQLite on Render:

1. Attach a persistent disk to the web service at `/var/data`.
2. Set `DATABASE_PATH=/var/data/bwd_enquiries.db`.
3. Set `APP_ENV=production`, both session secrets, and `RATELIMIT_STORAGE_URI` to the private Redis-compatible URL from a Redis/Key Value service.
4. Set `TRUST_PROXY_HEADERS=true` if the service is behind Render's trusted reverse proxy.
5. Use build command `pip install -r requirements.txt` and start command `gunicorn app:app`.
6. Keep a disk-backed SQLite deployment to one Render service instance. Render documents that a persistent disk is available only to one service instance and that the rest of the filesystem remains ephemeral: https://render.com/docs/disks.

The persistent disk is available at runtime, not in a separate build or one-off job. Run the password-rotation command in the live service's runtime with the correct `DATABASE_PATH`.

## 6. Reverse proxy safety

Werkzeug `ProxyFix` is disabled unless `TRUST_PROXY_HEADERS=true`. Enable it only when one known reverse proxy overwrites `X-Forwarded-For` and `X-Forwarded-Proto`. Do not enable it on a directly exposed app server or where clients can supply these headers. If a host uses a different proxy chain, configure the trusted proxy counts to match that host before enabling proxy headers.

## 7. Pre-launch checks

- Run `python -m unittest discover -s tests -v`.
- Confirm `/` loads at mobile and desktop widths and that the Google Map shows the supplied location pin.
- Submit a test survey request and verify the admin dashboard shows **Pending Request**.
- Confirm an appointment; verify the date becomes unavailable.
- Cancel, complete, or archive the appointment; verify that the date is released according to the business rules.
- Confirm CSRF rejection, login rate limiting, and secure cookies over HTTPS.
- Restart/redeploy and verify enquiries and admin credentials remain intact.
- Test restoring a database backup.
- Verify `/robots.txt`, `/sitemap.xml`, the contact links, and all local media assets.
