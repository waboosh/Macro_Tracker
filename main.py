"""Application entry point: sets up the database, then launches the GUI."""

import os

import gui
from database import get_connection, initialize_database, seed_public_foods

DB_PATH = os.path.join(os.path.dirname(__file__), "macro_tracker.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "common_foods.csv")


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
