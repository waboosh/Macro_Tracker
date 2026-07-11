"""Application entry point: sets up the database, then launches the GUI."""

import os
import sys

import gui
from database import get_connection, initialize_database, seed_public_foods

if getattr(sys, "frozen", False):
    # Running as a PyInstaller build: keep the database next to the .exe so
    # logged data persists across runs, but read the seed CSV from the
    # bundled (read-only) temp extraction dir.
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(__file__)
    BUNDLE_DIR = APP_DIR

DB_PATH = os.path.join(APP_DIR, "macro_tracker.db")
CSV_PATH = os.path.join(BUNDLE_DIR, "data", "common_foods.csv")


def main():
    conn = get_connection(DB_PATH)
    if conn is None:
        return

    try:
        initialize_database(conn)
        seed_public_foods(conn, CSV_PATH)
        gui.main(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
