"""Compatibility helper for older Burgersfort Water Drilling databases."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "bwd_enquiries.db"

with sqlite3.connect(DB) as connection:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(enquiries)")}
    if "status" not in columns:
        connection.execute("ALTER TABLE enquiries ADD COLUMN status TEXT NOT NULL DEFAULT 'New'")
    if "is_deleted" not in columns:
        connection.execute("ALTER TABLE enquiries ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")
    connection.commit()

print("Burgersfort Water Drilling enquiry schema is ready.")
