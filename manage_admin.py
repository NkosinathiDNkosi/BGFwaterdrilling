"""Interactive administrator bootstrap/password rotation utility.

Usage: python manage_admin.py set-password [username]
Run this in the same environment and with the same DATABASE_PATH as the web app.
"""
from __future__ import annotations

import getpass
import sys

from database import init_database, set_admin_password


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "set-password":
        print("Usage: python manage_admin.py set-password [username]")
        return 2

    username = sys.argv[2].strip() if len(sys.argv) > 2 else input("Administrator username: ").strip()
    password = getpass.getpass("New administrator password (min. 14 characters): ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    try:
        init_database()
        created = set_admin_password(username, password)
    except (ValueError, RuntimeError) as exc:
        print(f"Could not update administrator: {exc}", file=sys.stderr)
        return 1

    print(f"Administrator {'created' if created else 'password rotated'} successfully for '{username}'.")
    print("Remove any temporary ADMIN_PASSWORD environment variable after initial setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
