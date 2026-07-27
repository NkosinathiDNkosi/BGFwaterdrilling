"""Burgersfort Water Drilling website and lightweight lead-management dashboard."""

import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    Response,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple


# -----------------------------------------------------------------------------
# Flask configuration
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bwd_enquiries.db")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    os.urandom(32).hex(),
)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
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

STATUSES = ["New", "Contacted", "Quoted", "Scheduled", "Completed"]


# -----------------------------------------------------------------------------
# Database helpers
# -----------------------------------------------------------------------------
def get_db_connection():
    """Return a SQLite connection whose rows behave like dictionaries."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the enquiry and admin tables when the app starts."""
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            location TEXT NOT NULL,
            preferred_drilling_date TEXT,
            service TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL
        )
        """
    )

    # Safely upgrade databases created by an earlier version of the website.
    columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(enquiries)").fetchall()
    }
    if "preferred_drilling_date" not in columns:
        cursor.execute(
            "ALTER TABLE enquiries ADD COLUMN preferred_drilling_date TEXT"
        )

    # SQLite allows multiple NULL values, so old enquiries remain valid while
    # every newly selected drilling date is protected against double-booking.
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            unique_enquiry_drilling_date
        ON enquiries(preferred_drilling_date)
        WHERE preferred_drilling_date IS NOT NULL
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )

    # Create the first admin from environment variables when none exists.
    # Configure ADMIN_USERNAME and ADMIN_PASSWORD in Render before deployment.
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    admin_exists = cursor.execute(
        "SELECT id FROM admins WHERE username = ?", (admin_username,)
    ).fetchone()
    if not admin_exists:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (admin_username, generate_password_hash(admin_password)),
        )

    connection.commit()
    connection.close()


init_db()


@app.after_request
def add_response_headers(response):
    """Add practical security and caching headers for production delivery."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
    return response


# -----------------------------------------------------------------------------
# Validation and authentication helpers
# -----------------------------------------------------------------------------
def valid_phone(phone):
    """Accept standard South African mobile and landline number formats."""
    cleaned = re.sub(r"[^\d+]", "", phone)
    return bool(re.fullmatch(r"(?:\+27|0)\d{9}", cleaned))


def get_available_drilling_dates(days=90):
    """Return unbooked dates from tomorrow through the requested date window."""
    today = date.today()
    last_day = today + timedelta(days=days)
    connection = get_db_connection()
    booked_dates = {
        row["preferred_drilling_date"]
        for row in connection.execute(
            """
            SELECT preferred_drilling_date
            FROM enquiries
            WHERE preferred_drilling_date IS NOT NULL
            """
        ).fetchall()
    }
    connection.close()

    available_dates = []
    current_day = today + timedelta(days=1)
    while current_day <= last_day:
        iso_date = current_day.isoformat()
        if iso_date not in booked_dates:
            available_dates.append(
                {
                    "value": iso_date,
                    "label": current_day.strftime("%A, %d %B %Y"),
                }
            )
        current_day += timedelta(days=1)
    return available_dates


def login_required(view_function):
    """Protect dashboard routes from unauthenticated visitors."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapped_view


# -----------------------------------------------------------------------------
# Public website routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    # Use Flask's response helper directly because the exported ``app`` object
    # is wrapped by DispatcherMiddleware after all routes are registered.
    response = make_response(render_template(
        "index.html",
        services=SERVICES,
        available_dates=get_available_drilling_dates(),
        year=datetime.now().year,
    ))
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    return response


@app.route("/submit-enquiry", methods=["POST"])
def submit_enquiry():
    """Validate and store a prospective client's site enquiry."""
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    location = request.form.get("location", "").strip()
    preferred_drilling_date = request.form.get(
        "preferred_drilling_date", ""
    ).strip()
    service = request.form.get("service", "").strip()
    message = request.form.get("message", "").strip()

    if len(full_name) < 2 or not valid_phone(phone) or not location:
        flash("Please enter your name, home address and a valid South African phone number.", "error")
        return redirect(url_for("index", _anchor="contact"))

    try:
        requested_date = date.fromisoformat(preferred_drilling_date)
    except ValueError:
        requested_date = None

    first_available_day = date.today() + timedelta(days=1)
    last_available_day = date.today() + timedelta(days=90)
    if (
        requested_date is None
        or requested_date < first_available_day
        or requested_date > last_available_day
    ):
        flash("Please choose one of the available drilling dates.", "error")
        return redirect(url_for("index", _anchor="contact"))

    if service not in SERVICES:
        service = "General Enquiry"

    connection = get_db_connection()
    try:
        # BEGIN IMMEDIATE serialises competing writes. The unique index remains
        # the final safeguard if two visitors submit the same date together.
        connection.execute("BEGIN IMMEDIATE")
        already_booked = connection.execute(
            """
            SELECT id FROM enquiries
            WHERE preferred_drilling_date = ?
            """,
            (preferred_drilling_date,),
        ).fetchone()
        if already_booked:
            connection.rollback()
            flash(
                "That drilling date has just been booked. Please select another available date.",
                "error",
            )
            return redirect(url_for("index", _anchor="contact"))

        connection.execute(
            """
            INSERT INTO enquiries
                (full_name, phone, email, location, preferred_drilling_date,
                 service, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'New', ?)
            """,
            (
                full_name,
                phone,
                email,
                location,
                preferred_drilling_date,
                service,
                message,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        flash(
            "That drilling date has just been booked. Please select another available date.",
            "error",
        )
        return redirect(url_for("index", _anchor="contact"))
    finally:
        connection.close()

    flash(
        "Thank you. Your preferred drilling date has been reserved and our team will contact you shortly.",
        "success",
    )
    return redirect(url_for("index", _anchor="contact"))


# -----------------------------------------------------------------------------
# Admin routes
# -----------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()
        admin = connection.execute(
            "SELECT * FROM admins WHERE username = ?", (username,)
        ).fetchone()
        connection.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(url_for("dashboard"))

        error = "Incorrect username or password."

    return render_template("login.html", error=error)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@login_required
def dashboard():
    connection = get_db_connection()
    enquiries = connection.execute(
        "SELECT * FROM enquiries ORDER BY created_at DESC"
    ).fetchall()
    connection.close()

    stats = {
        "total": len(enquiries),
        "new": sum(item["status"] == "New" for item in enquiries),
        "quoted": sum(item["status"] == "Quoted" for item in enquiries),
        "scheduled": sum(item["status"] == "Scheduled" for item in enquiries),
    }

    return render_template(
        "dashboard.html",
        enquiries=enquiries,
        statuses=STATUSES,
        stats=stats,
    )


@app.route("/admin/status/<int:enquiry_id>", methods=["POST"])
@login_required
def update_status(enquiry_id):
    status = request.form.get("status", "New")
    if status not in STATUSES:
        status = "New"

    connection = get_db_connection()
    connection.execute(
        "UPDATE enquiries SET status = ? WHERE id = ?", (status, enquiry_id)
    )
    connection.commit()
    connection.close()
    return redirect(url_for("dashboard"))


@app.route("/admin/delete/<int:enquiry_id>", methods=["POST"])
@login_required
def delete_enquiry(enquiry_id):
    connection = get_db_connection()
    connection.execute("DELETE FROM enquiries WHERE id = ?", (enquiry_id,))
    connection.commit()
    connection.close()
    return redirect(url_for("dashboard"))


# -----------------------------------------------------------------------------
# SEO support routes
# -----------------------------------------------------------------------------
@app.route("/robots.txt")
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "Sitemap: https://burgersfortwaterdrilling.co.za/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    today = datetime.now().strftime("%Y-%m-%d")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://burgersfortwaterdrilling.co.za/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(content, mimetype="application/xml")


# Mount the polished operations dashboard at /admin while keeping the public
# website as the primary application. Render should continue using app:app.
public_app = app
from admin.admin_app import app as admin_app

app = DispatcherMiddleware(public_app, {"/admin": admin_app})


if __name__ == "__main__":
    run_simple(
        "0.0.0.0",
        int(os.environ.get("PORT", 5000)),
        app,
        use_reloader=os.environ.get("FLASK_DEBUG") == "1",
        use_debugger=os.environ.get("FLASK_DEBUG") == "1",
    )
