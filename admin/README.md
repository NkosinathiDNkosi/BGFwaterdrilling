# Burgersfort Water Drilling Admin

A custom operations dashboard for managing website enquiries, drilling quotes and project progress.

## Run locally

From the project root:

```bash
python admin/admin_app.py
```

Open `http://127.0.0.1:5001`.

Default login:

- Username: `admin`
- Password: `Admin@123`

For production, this application is mounted by the main `app.py` at `/admin`.
Render should use `gunicorn app:app`. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`
and `FLASK_SECRET_KEY` environment variables.

The admin uses the main project database: `bwd_enquiries.db`.
