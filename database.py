import sqlite3
import csv

def get_connection(db_path):
    """Create a connection to the SQLite database specified by db_path."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")  # Enable foreign key support
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def initialize_database(conn):
    """Initialize the database with necessary tables."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS foods(
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       name TEXT NOT NULL,
                       serving_size REAL NOT NULL, 
                       serving_unit TEXT NOT NULL,  
                       calories REAL NOT NULL,
                       protein REAL NOT NULL,
                       carbs REAL NOT NULL,
                       fat REAL NOT NULL,
                       source TEXT)
                       """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_entries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                servings REAL NOT NULL,
                FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE)
                       """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")

def add_food(conn, name, serving_size, serving_unit, calories, protein, carbs, fat, source):
    """Add a new food item to the foods table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO foods (name, serving_size, serving_unit, calories, protein, carbs, fat, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, serving_size, serving_unit, calories, protein, carbs, fat, source))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding food: {e}")

def get_all_foods(conn):
    """Retrieve all food items from the foods table."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM foods")
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error retrieving foods: {e}")
        return []

def search_foods_by_name(conn, name):
    """Search for food items by name."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM foods WHERE name LIKE ?", ('%' + name + '%',))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error searching foods: {e}")
        return []
    
def add_log_entry(conn, food_id, date, meal_type, servings):
    """Add a new log entry to the log_entries table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO log_entries (food_id, date, meal_type, servings)
            VALUES (?, ?, ?, ?)
        """, (food_id, date, meal_type, servings))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding log entry: {e}")

def get_log_entries_by_date(conn, date):
    """Retrieve all log entries for a specific date."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT le.id, f.name, le.date, le.meal_type, le.servings
            FROM log_entries le
            JOIN foods f ON le.food_id = f.id
            WHERE le.date = ?
        """, (date,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error retrieving log entries: {e}")
        return []
    
def delete_log_entry(conn, log_entry_id):
    """Delete a log entry by its ID."""
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM log_entries WHERE id = ?", (log_entry_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error deleting log entry: {e}")

def seed_public_foods(conn, csv_path):
    """Seed the foods table with public data from a CSV file, only if empty."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM foods")
        count = cursor.fetchone()[0]  # get the count out of the fetched result

        if count > 0:
            print("Foods table already seeded, skipping.")
            return

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                add_food(
                    conn,
                    row["name"],
                    float(row["serving_size"]),   # serving_size
                    row["serving_unit"],           # serving_unit
                    float(row["calories"]),    # calories
                    float(row["protein_g"]),    # protein_g
                    float(row["carbs_g"]),    # carbs_g
                    float(row["fat_g"]),    # fat_g
                    row["source"]             # source
                )
        print("Public foods seeded successfully.")
    except sqlite3.Error as e:
        print(f"Error seeding foods: {e}")
    except FileNotFoundError:
        print(f"CSV file not found at {csv_path}")

def import_custom_foods(conn, csv_path):
    """Import a user-provided CSV of foods, tagging them as 'custom'. 
    Skips bad rows instead of failing the whole import."""
    required_columns = {"name", "serving_size", "serving_unit", "calories", "protein_g", "carbs_g", "fat_g"}
    success_count = 0
    errors = []

    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)

            if not required_columns.issubset(reader.fieldnames):
                missing = required_columns - set(reader.fieldnames)
                print(f"CSV is missing required columns: {missing}")
                return 0, [f"Missing required columns: {missing}"]

            for row_num, row in enumerate(reader, start=2):  # start=2 since row 1 is the header
                try:
                    add_food(
                        conn,
                        row["name"],
                        float(row["serving_size"]),
                        row["serving_unit"],
                        float(row["calories"]),
                        float(row["protein_g"]),
                        float(row["carbs_g"]),
                        float(row["fat_g"]),
                        "custom"  # force custom, regardless of what the CSV says
                    )
                    success_count += 1
                except (ValueError, KeyError) as e:
                    errors.append(f"Row {row_num}: {e}")

    except FileNotFoundError:
        print(f"CSV file not found at {csv_path}")
        return 0, [f"File not found: {csv_path}"]

    print(f"Imported {success_count} foods, {len(errors)} rows skipped.")
    return success_count, errors

def get_daily_macro_totals(conn, date):
    """Sum calories/protein/carbs/fat across all logged foods for a given date,
    accounting for servings."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SUM(f.calories * le.servings), 
               SUM(f.protein * le.servings),
               SUM(f.carbs * le.servings),
               SUM(f.fat * le.servings)
        FROM log_entries le
        JOIN foods f ON le.food_id = f.id
        WHERE le.date = ?
    """, (date,))
    return cursor.fetchone()  # (total_calories, total_protein, total_carbs, total_fat)

