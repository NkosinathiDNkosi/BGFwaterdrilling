"""Burgersfort Water Drilling public website and mounted admin dashboard."""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, Response, flash, make_response, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.serving import run_simple

from database import get_db_connection, init_database
from security_config import is_production, rate_limit_storage_uri, secret_key_from_env

app = Flask(__name__)
# Trust forwarded client/scheme headers only when this application is behind a
# known reverse proxy that overwrites them. Direct/local deployments leave this off.
if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config.update(
    SECRET_KEY=secret_key_from_env("FLASK_SECRET_KEY"),
    SESSION_COOKIE_NAME="bwd_public_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_production(),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=64 * 1024,
    WTF_CSRF_TIME_LIMIT=timedelta(hours=2),
)
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=rate_limit_storage_uri(),
    headers_enabled=True,
)

SERVICES = [
    "Borehole Drilling",
    "Borehole Installation",
    "PVC Casing Installation",
    "Pump Installation",
    "JoJo Tank Installation",
    "Complete Water System",
    "Water Survey / Site Assessment",
    "Maintenance & Repairs",
]


def valid_phone(phone: str) -> bool:
    """Accept common South African mobile and landline formats."""
    cleaned = re.sub(r"[^\d+]", "", phone)
    return bool(re.fullmatch(r"(?:\+27|0)\d{9}", cleaned))


def get_available_drilling_dates(days: int = 90) -> list[dict[str, str]]:
    """Return dates not currently occupied by an active confirmed appointment."""
    today = date.today()
    last_day = today + timedelta(days=days)
    connection = get_db_connection()
    try:
        booked_dates = {
            row["preferred_drilling_date"]
            for row in connection.execute(
                """
                SELECT preferred_drilling_date
                FROM enquiries
                WHERE preferred_drilling_date IS NOT NULL
                  AND appointment_status = 'Confirmed'
                  AND is_deleted = 0
                """
            ).fetchall()
        }
    finally:
        connection.close()

    available_dates = []
    current_day = today + timedelta(days=1)
    while current_day <= last_day:
        iso_date = current_day.isoformat()
        if iso_date not in booked_dates:
            available_dates.append({
                "value": iso_date,
                "label": current_day.strftime("%A, %d %B %Y"),
            })
        current_day += timedelta(days=1)
    return available_dates


@app.after_request
def add_response_headers(response):
    """Set practical baseline security and asset-cache headers."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
    if is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(error: CSRFError):
    return (
        "Your form session has expired or could not be verified. Please reload the page and try again.",
        400,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/")
def index():
    response = make_response(render_template(
        "index.html",
        services=SERVICES,
        available_dates=get_available_drilling_dates(),
        year=datetime.now().year,
    ))
    # The HTML contains a session-bound CSRF token; do not cache it in shared caches.
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/submit-enquiry", methods=["POST"])
@limiter.limit("8 per hour")
def submit_enquiry():
    """Create an enquiry with a pending appointment request, never a reservation."""
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    location = request.form.get("location", "").strip()
    requested_date_text = request.form.get("preferred_drilling_date", "").strip()
    service = request.form.get("service", "").strip()
    message = request.form.get("message", "").strip()

    email_is_valid = not email or bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))
    if (
        not 2 <= len(full_name) <= 120
        or not valid_phone(phone)
        or not 2 <= len(location) <= 250
        or not email_is_valid
        or len(email) > 254
        or len(message) > 3000
    ):
        flash(
            "Please check your name, phone number, email and property address, then try again.",
            "error",
        )
        return redirect(url_for("index", _anchor="contact"))

    try:
        requested_date = date.fromisoformat(requested_date_text)
    except ValueError:
        requested_date = None

    first_available_day = date.today() + timedelta(days=1)
    last_available_day = date.today() + timedelta(days=90)
    if requested_date is None or not first_available_day <= requested_date <= last_available_day:
        flash("Please choose a preferred date within the available 90-day window.", "error")
        return redirect(url_for("index", _anchor="contact"))

    if service not in SERVICES:
        service = "General Enquiry"

    connection = get_db_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        confirmed = connection.execute(
            """
            SELECT id FROM enquiries
            WHERE preferred_drilling_date = ?
              AND appointment_status = 'Confirmed'
              AND is_deleted = 0
            LIMIT 1
            """,
            (requested_date_text,),
        ).fetchone()
        if confirmed:
            connection.rollback()
            flash(
                "That date has already been confirmed for another job. Please choose a different preferred date.",
                "error",
            )
            return redirect(url_for("index", _anchor="contact"))

        connection.execute(
            """
            INSERT INTO enquiries
                (full_name, phone, email, location, preferred_drilling_date,
                 service, message, status, appointment_status, is_deleted, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'New', 'Pending Request', 0, ?)
            """,
            (
                full_name,
                phone,
                email or None,
                location,
                requested_date_text,
                service,
                message or None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Could not save a website enquiry")
        flash("We could not save your request right now. Please call or WhatsApp us directly.", "error")
        return redirect(url_for("index", _anchor="contact"))
    finally:
        connection.close()

    flash(
        "Thank you. We received your site-survey request. Your preferred date is pending confirmation; our team will contact you to confirm availability.",
        "success",
    )
    return redirect(url_for("index", _anchor="contact"))


@app.route("/healthz")
def healthz():
    """Minimal platform-agnostic health probe; never expose database details."""
    connection = get_db_connection()
    try:
        connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        app.logger.exception("Health check failed: database unavailable")
        return Response("unavailable", status=503, mimetype="text/plain")
    finally:
        connection.close()
    return Response("ok", status=200, mimetype="text/plain")


@app.route("/robots.txt")
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "Sitemap: https://bgfwaterdrilling.co.za/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://bgfwaterdrilling.co.za/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(content, mimetype="application/xml")


# Schema migrations run on every process start; migrations are serialized by SQLite.
init_database()

# Mount the separate admin Flask app after the public routes are registered.
public_app = app
from admin.admin_app import app as admin_app  # noqa: E402

app = DispatcherMiddleware(public_app, {"/admin": admin_app})

if __name__ == "__main__":
    debug_requested = os.environ.get("FLASK_DEBUG") == "1"
    if debug_requested and is_production():
        raise RuntimeError("FLASK_DEBUG must not be enabled when APP_ENV=production.")
    run_simple(
        "0.0.0.0",
        int(os.environ.get("PORT", 5000)),
        app,
        use_reloader=debug_requested,
        use_debugger=debug_requested,
    )
