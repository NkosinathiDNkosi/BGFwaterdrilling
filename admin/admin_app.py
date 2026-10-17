"""Secure, separately mounted Flask operations dashboard for website enquiries."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from database import get_db_connection, init_database
from security_config import is_production, rate_limit_storage_uri, secret_key_from_env

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=secret_key_from_env("ADMIN_SECRET_KEY"),
    SESSION_COOKIE_NAME="bwd_admin_session",
    SESSION_COOKIE_PATH="/admin",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_production(),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=64 * 1024,
    WTF_CSRF_TIME_LIMIT=timedelta(hours=2),
)
# Trust forwarded headers only behind the configured reverse proxy.
if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=rate_limit_storage_uri(),
    headers_enabled=True,
)

STATUSES = ["New", "Contacted", "Quoted", "Scheduled", "Completed", "Cancelled"]
APPOINTMENT_STATUSES = ["Pending Request", "Confirmed", "Cancelled", "Completed"]


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cache-Control", "no-store")
    if is_production():
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(error: CSRFError):
    return (
        "Your admin form session has expired or could not be verified. Reload the page and try again.",
        400,
        {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"},
    )


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
    parsed = parse_date(value)
    return parsed.strftime("%d %b %Y · %H:%M") if parsed else (value or "—")


@app.template_filter("initials")
def initials(value: str | None) -> str:
    words = (value or "?").split()
    return "".join(word[0].upper() for word in words[:2]) or "?"


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute; 20 per hour", methods=["POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with closing(get_db_connection()) as connection:
            admin = connection.execute(
                "SELECT id, username, password_hash FROM admins WHERE username = ?",
                (username,),
            ).fetchone()

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session.permanent = True
            session["admin_logged_in"] = True
            session["admin_username"] = admin["username"]
            session["admin_id"] = admin["id"]
            return redirect(url_for("dashboard"))

        # Keep the response generic so it does not reveal whether a username exists.
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")


@app.post("/logout")
@admin_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@admin_required
def dashboard():
    query = request.args.get("q", "").strip()[:200]
    status = request.args.get("status", "all").strip()
    service = request.args.get("service", "all").strip()

    where = ["is_deleted = 0"]
    params: list[str] = []
    if query:
        wildcard = f"%{query}%"
        where.append("(full_name LIKE ? OR phone LIKE ? OR email LIKE ? OR location LIKE ? OR message LIKE ?)")
        params.extend([wildcard] * 5)
    if status != "all" and status in STATUSES:
        where.append("status = ?")
        params.append(status)
    else:
        status = "all"
    if service != "all":
        where.append("service = ?")
        params.append(service)

    with closing(get_db_connection()) as connection:
        enquiries = connection.execute(
            f"SELECT * FROM enquiries WHERE {' AND '.join(where)} ORDER BY created_at DESC",
            params,
        ).fetchall()
        all_active = connection.execute(
            "SELECT * FROM enquiries WHERE is_deleted = 0 ORDER BY created_at DESC"
        ).fetchall()
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

    return render_template(
        "dashboard.html",
        enquiries=enquiries,
        recent=all_active[:5],
        totals=totals,
        statuses=STATUSES,
        appointment_statuses=APPOINTMENT_STATUSES,
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
    with closing(get_db_connection()) as connection:
        enquiry = connection.execute(
            "SELECT * FROM enquiries WHERE id = ? AND is_deleted = 0", (enquiry_id,)
        ).fetchone()
    if not enquiry:
        flash("Active enquiry not found.", "danger")
        return redirect(url_for("dashboard"))
    return render_template(
        "detail.html",
        enquiry=enquiry,
        statuses=STATUSES,
        appointment_statuses=APPOINTMENT_STATUSES,
    )


@app.post("/enquiry/<int:enquiry_id>/status")
@admin_required
def update_status(enquiry_id: int):
    status = request.form.get("status", "New")
    if status not in STATUSES:
        flash("Invalid workflow status selected.", "danger")
        return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))

    with closing(get_db_connection()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            enquiry = connection.execute(
                "SELECT status, appointment_status, preferred_drilling_date, is_deleted "
                "FROM enquiries WHERE id = ?",
                (enquiry_id,),
            ).fetchone()
            if not enquiry or enquiry["is_deleted"]:
                connection.rollback()
                flash("Active enquiry not found.", "danger")
                return redirect(url_for("dashboard"))

            appointment_status = enquiry["appointment_status"]
            if status == "Scheduled":
                if not enquiry["preferred_drilling_date"]:
                    connection.rollback()
                    flash("This enquiry has no preferred date and cannot be scheduled yet.", "warning")
                    return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))
                appointment_status = "Confirmed"
            elif status == "Cancelled":
                appointment_status = "Cancelled"
            elif status == "Completed":
                appointment_status = "Completed"
            elif enquiry["appointment_status"] == "Confirmed":
                # Moving a previously scheduled lead back into the enquiry pipeline
                # releases the date until it is explicitly confirmed again.
                appointment_status = "Pending Request"

            connection.execute(
                "UPDATE enquiries SET status = ?, appointment_status = ? WHERE id = ?",
                (status, appointment_status, enquiry_id),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            flash("That date is already confirmed for another job. Choose a different date first.", "danger")
            return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))
        except Exception:
            connection.rollback()
            raise

    flash("Enquiry workflow updated.", "success")
    return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))


@app.post("/enquiry/<int:enquiry_id>/appointment")
@admin_required
def update_appointment(enquiry_id: int):
    new_appointment_status = request.form.get("appointment_status", "")
    if new_appointment_status not in APPOINTMENT_STATUSES:
        flash("Invalid appointment status selected.", "danger")
        return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))

    with closing(get_db_connection()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            enquiry = connection.execute(
                "SELECT status, appointment_status, preferred_drilling_date, is_deleted "
                "FROM enquiries WHERE id = ?",
                (enquiry_id,),
            ).fetchone()
            if not enquiry or enquiry["is_deleted"]:
                connection.rollback()
                flash("Active enquiry not found.", "danger")
                return redirect(url_for("dashboard"))
            if new_appointment_status == "Confirmed" and not enquiry["preferred_drilling_date"]:
                connection.rollback()
                flash("A preferred date is required before confirming an appointment.", "warning")
                return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))

            # Confirming is the only action that blocks a preferred date. The
            # database partial unique index is the final concurrent-write guard.
            new_workflow_status = enquiry["status"]
            if new_appointment_status == "Confirmed":
                new_workflow_status = "Scheduled"
            elif new_appointment_status == "Cancelled" and new_workflow_status == "Scheduled":
                new_workflow_status = "Cancelled"
            elif new_appointment_status == "Pending Request" and new_workflow_status == "Scheduled":
                new_workflow_status = "Contacted"
            elif new_appointment_status == "Completed":
                new_workflow_status = "Completed"

            connection.execute(
                "UPDATE enquiries SET appointment_status = ?, status = ? WHERE id = ?",
                (new_appointment_status, new_workflow_status, enquiry_id),
            )
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            flash("That date has already been confirmed for another job. The appointment was not changed.", "danger")
            return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))
        except Exception:
            connection.rollback()
            raise

    messages = {
        "Pending Request": "Appointment request is pending. The preferred date is available for other requests.",
        "Confirmed": "Appointment confirmed. This date is now blocked for other jobs.",
        "Cancelled": "Appointment cancelled. The preferred date has been released.",
        "Completed": "Appointment marked completed. The preferred date is no longer blocked.",
    }
    flash(messages[new_appointment_status], "success")
    return redirect(url_for("enquiry_detail", enquiry_id=enquiry_id))


@app.post("/enquiry/<int:enquiry_id>/trash")
@admin_required
def trash_enquiry(enquiry_id: int):
    with closing(get_db_connection()) as connection:
        connection.execute(
            """UPDATE enquiries
               SET is_deleted = 1,
                   appointment_status = CASE
                     WHEN appointment_status = 'Confirmed' THEN 'Cancelled'
                     ELSE appointment_status
                   END
               WHERE id = ? AND is_deleted = 0""",
            (enquiry_id,),
        )
        connection.commit()
    flash("Enquiry moved to Trash. Any confirmed date has been released.", "success")
    return redirect(url_for("dashboard"))


@app.route("/trash")
@admin_required
def trash():
    with closing(get_db_connection()) as connection:
        enquiries = connection.execute(
            "SELECT * FROM enquiries WHERE is_deleted = 1 ORDER BY created_at DESC"
        ).fetchall()
    return render_template("trash.html", enquiries=enquiries)


@app.post("/enquiry/<int:enquiry_id>/restore")
@admin_required
def restore_enquiry(enquiry_id: int):
    with closing(get_db_connection()) as connection:
        connection.execute(
            "UPDATE enquiries SET is_deleted = 0 WHERE id = ? AND is_deleted = 1",
            (enquiry_id,),
        )
        connection.commit()
    flash("Enquiry restored. A previously confirmed appointment stays released until reconfirmed.", "success")
    return redirect(url_for("trash"))


@app.post("/enquiry/<int:enquiry_id>/delete")
@admin_required
def delete_enquiry(enquiry_id: int):
    with closing(get_db_connection()) as connection:
        connection.execute(
            "DELETE FROM enquiries WHERE id = ? AND is_deleted = 1", (enquiry_id,)
        )
        connection.commit()
    flash("Enquiry permanently deleted.", "success")
    return redirect(url_for("trash"))


def _safe_csv_cell(value):
    """Prevent spreadsheet formula execution when a CSV is opened interactively."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@app.route("/export.csv")
@admin_required
def export_csv():
    with closing(get_db_connection()) as connection:
        rows = connection.execute(
            "SELECT * FROM enquiries WHERE is_deleted = 0 ORDER BY created_at DESC"
        ).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Name", "Phone", "Email", "Home Address", "Preferred Drilling Date",
        "Service", "Message", "Workflow Status", "Appointment Status", "Created",
    ])
    for row in rows:
        writer.writerow([_safe_csv_cell(row[key]) for key in (
            "id", "full_name", "phone", "email", "location", "preferred_drilling_date",
            "service", "message", "status", "appointment_status", "created_at",
        )])
    return Response(output.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=burgersfort-water-drilling-enquiries.csv",
        "Cache-Control": "no-store",
    })


# Safe for this module to be launched directly, while app.py also calls it before mount.
init_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=os.getenv("FLASK_DEBUG") == "1")
