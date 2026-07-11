"""Create and seed the local SQLite database (run this once to get started)."""

import os

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
        print(f"Database ready at {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
