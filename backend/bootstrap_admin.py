"""One-time secure first-admin setup: python -m backend.bootstrap_admin"""
import getpass
import re
import sqlite3
from .auth import hash_password
from .database import connect


def main():
    print("Create the initial CineMatch administrator (one time only).")
    name = input("Name: ").strip()
    email = input("Email: ").strip().lower()
    if not name or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise SystemExit("Enter a name and valid email address.")
    password = getpass.getpass("Password (12+ characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 12 or password != confirm:
        raise SystemExit("Password must be at least 12 characters and both entries must match.")
    try:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone():
                raise SystemExit("An administrator already exists. Bootstrap is disabled.")
            db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')",
                       (name, email, hash_password(password)))
    except sqlite3.IntegrityError:
        raise SystemExit("That email is already registered.")
    print("Administrator created. Log in through the CineMatch website.")


if __name__ == "__main__":
    main()
