"""Regression tests for appointment date reservations and legacy DB migrations."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseBookingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.env_patch = patch.dict(os.environ, {"ADMIN_USERNAME": "", "ADMIN_PASSWORD": ""})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.path_patch = patch.object(database, "DATABASE_PATH", self.db_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        database.init_database()

    def _insert_enquiry(self, name: str, day: str) -> int:
        connection = database.get_db_connection()
        try:
            cursor = connection.execute(
                """INSERT INTO enquiries
                   (full_name, phone, location, service, preferred_drilling_date,
                    status, appointment_status, is_deleted, created_at)
                   VALUES (?, '0818021758', 'Burgersfort', 'Borehole Drilling', ?,
                           'New', 'Pending Request', 0, datetime('now'))""",
                (name, day),
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()

    def test_pending_requests_do_not_reserve_date_but_confirmed_ones_do(self):
        date_value = "2098-01-15"
        first_id = self._insert_enquiry("Client One", date_value)
        second_id = self._insert_enquiry("Client Two", date_value)

        connection = database.get_db_connection()
        try:
            connection.execute(
                "UPDATE enquiries SET appointment_status = 'Confirmed', status = 'Scheduled' WHERE id = ?",
                (first_id,),
            )
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE enquiries SET appointment_status = 'Confirmed', status = 'Scheduled' WHERE id = ?",
                    (second_id,),
                )
                connection.commit()
            connection.rollback()

            connection.execute(
                "UPDATE enquiries SET appointment_status = 'Cancelled', status = 'Cancelled' WHERE id = ?",
                (first_id,),
            )
            connection.execute(
                "UPDATE enquiries SET appointment_status = 'Confirmed', status = 'Scheduled' WHERE id = ?",
                (second_id,),
            )
            connection.commit()
            confirmed_count = connection.execute(
                """SELECT COUNT(*) FROM enquiries
                   WHERE preferred_drilling_date = ? AND appointment_status = 'Confirmed'
                     AND is_deleted = 0""",
                (date_value,),
            ).fetchone()[0]
            self.assertEqual(confirmed_count, 1)

            connection.execute(
                "UPDATE enquiries SET is_deleted = 1, appointment_status = 'Cancelled' WHERE id = ?",
                (second_id,),
            )
            connection.commit()
            active_confirmed_count = connection.execute(
                """SELECT COUNT(*) FROM enquiries
                   WHERE preferred_drilling_date = ? AND appointment_status = 'Confirmed'
                     AND is_deleted = 0""",
                (date_value,),
            ).fetchone()[0]
            self.assertEqual(active_confirmed_count, 0)
        finally:
            connection.close()

    def test_old_schema_migrates_scheduled_rows_and_drops_old_unique_index(self):
        old_path = Path(self.temp_dir.name) / "legacy.db"
        legacy = sqlite3.connect(old_path)
        legacy.executescript(
            """
            CREATE TABLE enquiries (
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
            );
            CREATE UNIQUE INDEX unique_enquiry_drilling_date
                ON enquiries(preferred_drilling_date)
                WHERE preferred_drilling_date IS NOT NULL;
            CREATE TABLE admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            INSERT INTO enquiries(full_name, phone, location, preferred_drilling_date,
                                  service, status, created_at)
            VALUES ('Legacy Scheduled', '0818021758', 'Burgersfort', '2098-01-16',
                    'Borehole Drilling', 'Scheduled', '2026-01-01 10:00:00');
            """
        )
        legacy.commit()
        legacy.close()

        with patch.object(database, "DATABASE_PATH", old_path):
            database.init_database()
            database.init_database()  # migration must be idempotent
            connection = database.get_db_connection()
            try:
                row = connection.execute(
                    "SELECT appointment_status, is_deleted FROM enquiries WHERE id = 1"
                ).fetchone()
                self.assertEqual(row["appointment_status"], "Confirmed")
                self.assertEqual(row["is_deleted"], 0)
                indexes = {
                    index[1]
                    for index in connection.execute("PRAGMA index_list(enquiries)").fetchall()
                }
                self.assertNotIn("unique_enquiry_drilling_date", indexes)
                self.assertIn("unique_confirmed_appointment_date", indexes)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
