from __future__ import annotations

import csv
import io
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Paths and application configuration — edit environment values, not secrets here.
ADMIN_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ADMIN_DIR.parent
DATABASE_PATH = PROJECT_DIR / "bwd_enquiries.db"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv(
    "ADMIN_SECRET_KEY",
    os.getenv("FLASK_SECRET_KEY", "burgersfort-water-drilling-admin-2026"),
)

STATUSES = ["New", "Contacted", "Quoted", "Scheduled", "Completed", "Cancelled"]


# Database setup and reusable helpers.
# -----------------------------------------------------------------------------
# Database connection and first-run schema setup
# -----------------------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_schema() -> None:
    with get_db_connection() as connection:
        connection.execute("""
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
                created_at TEXT NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(enquiries)")}
        if "is_deleted" not in columns:
            connection.execute("ALTER TABLE enquiries ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")
        if "preferred_drilling_date" not in columns:
            connection.execute("ALTER TABLE enquiries ADD COLUMN preferred_drilling_date TEXT")
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS unique_enquiry_drilling_date
            ON enquiries(preferred_drilling_date)
            WHERE preferred_drilling_date IS NOT NULL
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "Admin@123")
        if not connection.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone():
            connection.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
        connection.commit()


# -----------------------------------------------------------------------------
# Authentication, date formatting and template helpers
# -----------------------------------------------------------------------------
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please sign in to access the operations dashboard.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.fromisoformat(value) if fmt is None else datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@app.template_filter("pretty_date")
def pretty_date(value: str | None) -> str:
    date = parse_date(value)
    return date.strftime("%d %b %Y · %H:%M") if date else (value or "—")


@app.template_filter("initials")
def initials(value: str | None) -> str:
    words = (value or "?").split()
    return "".join(word[0].upper() for word in words[:2]) or "?"


# -----------------------------------------------------------------------------
# Authentication routes
# -----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db_connection() as connection:
            admin = connection.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")


# -----------------------------------------------------------------------------
# Dashboard, filtering and enquiry-management routes
# -----------------------------------------------------------------------------
@app.route("/")
@admin_required
def dashboard():
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip()
    service = request.args.get("service", "all").strip()

    where = ["is_deleted = 0"]
    params: list[str] = []
    if query:
        wildcard = f"%{query}%"
        where.append("(full_name LIKE ? OR phone LIKE ? OR email LIKE ? OR location LIKE ? OR message LIKE ?)")
        params.extend([wildcard] * 5)
    if status != "all":
        where.append("status = ?")
        params.append(status)
    if service != "all":
        where.append("service = ?")
        params.append(service)

    with get_db_connection() as connection:
        enquiries = connection.execute(
            f"SELECT * FROM enquiries WHERE {' AND '.join(where)} ORDER BY created_at DESC", params
        ).fetchall()
        all_active = connection.execute("SELECT * FROM enquiries WHERE is_deleted = 0").fetchall()
        services = [row[0] for row in connection.execute(
            "SELECT DISTINCT service FROM enquiries WHERE is_deleted = 0 ORDER BY service"
        ).fetchall()]

    totals = {name.lower(): sum(row["status"] == name for row in all_active) for name in STATUSES}
    totals["all"] = len(all_active)
    active_projects = totals["scheduled"]
    conversion = round((totals["completed"] / totals["all"] * 100), 1) if totals["all"] else 0

    recent_days = []
    for offset in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=offset)).date()
        count = sum(
            1 for row in all_active
            if parse_date(row["created_at"]) and parse_date(row["created_at"]).date() == day
        )
        recent_days.append({"label": day.strftime("%a"), "count": count})

    recent = all_active[:5]
    return render_template(
        "dashboard.html",
        enquiries=enquiries,
        recent=recent,
        totals=totals,
        statuses=STATUSES,
        services=services,
        active_status=status,
        active_service=service,
        query=query,
        day_counts=recent_days,
        active_projects=active_projects,
        conversion=conversion,
    )


@app.route("/enquiry/<int:enquiry_id>")
@admin_required
def enquiry_detail(enquiry_id: int):
    with get_db_connection() as connection:
        enquiry = connection.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
    if not enquiry:
        flash("Enquiry not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("detail.html", enquiry=enquiry, statuses=STATUSES)


@app.post("/enquiry/<int:enquiry_id>/status")
@admin_required
def update_status(enquiry_id: int):
    status = request.form.get("status", "New")
    if status not in STATUSES:
        flash("Invalid status selected.", "danger")
    else:
        with get_db_connection() as connection:
            connection.execute("UPDATE enquiries SET status = ? WHERE id = ?", (status, enquiry_id))
            connection.commit()
        flash("Enquiry status updated.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.post("/enquiry/<int:enquiry_id>/trash")
@admin_required
def trash_enquiry(enquiry_id: int):
    with get_db_connection() as connection:
        connection.execute("UPDATE enquiries SET is_deleted = 1 WHERE id = ?", (enquiry_id,))
        connection.commit()
    flash("Enquiry moved to Trash.", "success")
    return redirect(url_for("dashboard"))


@app.route("/trash")
@admin_required
def trash():
    with get_db_connection() as connection:
        enquiries = connection.execute(
            "SELECT * FROM enquiries WHERE is_deleted = 1 ORDER BY created_at DESC"
        ).fetchall()
    return render_template("trash.html", enquiries=enquiries)


@app.post("/enquiry/<int:enquiry_id>/restore")
@admin_required
def restore_enquiry(enquiry_id: int):
    with get_db_connection() as connection:
        connection.execute("UPDATE enquiries SET is_deleted = 0 WHERE id = ?", (enquiry_id,))
        connection.commit()
    flash("Enquiry restored.", "success")
    return redirect(url_for("trash"))


@app.post("/enquiry/<int:enquiry_id>/delete")
@admin_required
def delete_enquiry(enquiry_id: int):
    with get_db_connection() as connection:
        connection.execute("DELETE FROM enquiries WHERE id = ? AND is_deleted = 1", (enquiry_id,))
        connection.commit()
    flash("Enquiry permanently deleted.", "success")
    return redirect(url_for("trash"))


# -----------------------------------------------------------------------------
# CSV export and session logout
# -----------------------------------------------------------------------------
@app.route("/export.csv")
@admin_required
def export_csv():
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM enquiries WHERE is_deleted = 0 ORDER BY created_at DESC"
        ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Phone", "Email", "Home Address", "Estimated Drilling Date", "Service", "Message", "Status", "Created"])
    for row in rows:
        writer.writerow([row["id"], row["full_name"], row["phone"], row["email"], row["location"], row["preferred_drilling_date"], row["service"], row["message"], row["status"], row["created_at"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=burgersfort-water-drilling-enquiries.csv"
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


ensure_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=os.getenv("FLASK_DEBUG") == "1")
