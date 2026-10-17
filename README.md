# Burgersfort Water Drilling

A responsive Flask website for a local borehole-drilling and water-system business in Burgersfort, Limpopo. The repository contains the public website, an authenticated operations dashboard, enquiry handling, appointment-date management, and the business's real project media.

## Highlights

- Mobile-first public site with locally hosted project photographs and videos.
- Inline SVG icon system with no icon-font library dependency.
- Indicative drilling package calculator and WhatsApp enquiry links.
- Public site-survey request form with server-side validation and CSRF protection.
- Admin dashboard for enquiries, appointment confirmation, cancellation, completion, and archiving.
- Confirmed appointments alone reserve dates; pending requests may share a preferred date.
- Shared SQLite data layer, repeatable schema migration, configurable database path, and password-rotation command.
- Login and enquiry rate limiting, secure production session-cookie settings, and baseline HTTP security headers.
- SEO metadata, LocalBusiness/FAQ structured data, sitemap, robots policy, and accessible FAQ/lightbox interactions.

## Tech stack

- Python 3.10+
- Flask and Jinja templates
- SQLite (single-instance production deployments) or a separately adapted managed database backend
- Flask-WTF for CSRF protection
- Flask-Limiter with Redis-compatible storage for shared production rate limits
- Gunicorn for production WSGI serving on Linux/container hosts

## Run locally on Windows

Open Command Prompt or the VS Code terminal in this folder:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. On first run, a local SQLite database is created under `instance/`. Development-only session secrets are generated when not configured; they are temporary and should not be used for production.

Create or rotate the local admin user in a second terminal, after activating the same virtual environment:

```bat
python manage_admin.py set-password admin
```

The command prompts for the password and stores only its hash. Open `http://127.0.0.1:5000/admin/login` to sign in.

## Project structure

```text
.
├── app.py                      # Public Flask app and mounted /admin app
├── database.py                 # Shared SQLite connection and schema migrations
├── security_config.py          # Production secrets and limiter configuration
├── manage_admin.py             # Interactive admin creation/password rotation
├── requirements.txt
├── templates/                  # Public Jinja templates and inline SVG macro
├── static/                     # Public CSS, JavaScript, icons, and media
├── admin/
│   ├── admin_app.py            # Operations dashboard
│   ├── templates/
│   └── static/
├── tests/                      # Booking lifecycle and migration regressions
├── README.md
└── DEPLOYMENT.md
```

## Production configuration

Use the documented checklist in [DEPLOYMENT.md](DEPLOYMENT.md). The app is not tied to Render; it can run anywhere that supports Python/WSGI and provides a persistent database path plus a Redis-compatible rate-limit store. Render instructions are included only as one hosting option.

Minimum production configuration:

- `APP_ENV=production`
- `FLASK_SECRET_KEY` and `ADMIN_SECRET_KEY`: independent high-entropy random secrets
- `DATABASE_PATH`: absolute path on persistent storage
- `RATELIMIT_STORAGE_URI`: a private Redis-compatible URL shared by all workers
- `TRUST_PROXY_HEADERS=true` only when the service is behind one trusted reverse proxy that overwrites forwarded headers

Never commit `.env`, database files, customer exports, secrets, or `__pycache__` files. Keep all production credentials in the host’s secret/environment configuration.

## Tests

Run the standard-library regression tests from the project root:

```bat
python -m unittest discover -s tests -v
```

Then verify the website and admin workflow manually in a browser. Before production, confirm that an enquiry can be received, confirmed, cancelled, archived, and restored according to the operational rules; also test backups and recovery of the production database.
