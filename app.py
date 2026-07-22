"""Burgersfort Water Drilling website and lightweight lead-management dashboard."""

import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


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
            service TEXT NOT NULL,
            message TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL
        )
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

    # Create a starter admin account only when none exists.
    admin_exists = cursor.execute(
        "SELECT id FROM admins WHERE username = ?", ("admin",)
    ).fetchone()
    if not admin_exists:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("Admin@123")),
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
    response = app.make_response(render_template(
        "index.html",
        services=SERVICES,
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
    service = request.form.get("service", "").strip()
    message = request.form.get("message", "").strip()

    if len(full_name) < 2 or not valid_phone(phone) or not location:
        flash("Please enter your name, location and a valid South African phone number.", "error")
        return redirect(url_for("index", _anchor="contact"))

    if service not in SERVICES:
        service = "General Enquiry"

    connection = get_db_connection()
    connection.execute(
        """
        INSERT INTO enquiries
            (full_name, phone, email, location, service, message, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'New', ?)
        """,
        (
            full_name,
            phone,
            email,
            location,
            service,
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    connection.commit()
    connection.close()

    flash("Thank you. Our team will contact you shortly to discuss your site.", "success")
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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
