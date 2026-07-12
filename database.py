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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bodyweight_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                weight_lbs REAL NOT NULL)
                       """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile(
                id INTEGER PRIMARY KEY CHECK (id = 1),
                gender TEXT NOT NULL,
                height_in REAL NOT NULL,
                age INTEGER NOT NULL)
                       """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                food_id INTEGER NOT NULL,
                FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE)
                       """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_ingredients(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                food_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (food_id) REFERENCES foods(id))
                       """)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")

def add_food(conn, name, serving_size, serving_unit, calories, protein, carbs, fat, source):
    """Add a new food item to the foods table. Returns the new food's id, or None on error."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO foods (name, serving_size, serving_unit, calories, protein, carbs, fat, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, serving_size, serving_unit, calories, protein, carbs, fat, source))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error adding food: {e}")
        return None

def update_food(conn, food_id, name, serving_size, serving_unit, calories, protein, carbs, fat):
    """Overwrite an existing food's name/serving/macros in place (used to keep a recipe's
    virtual food row in sync with its current ingredients)."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE foods
            SET name = ?, serving_size = ?, serving_unit = ?, calories = ?, protein = ?, carbs = ?, fat = ?
            WHERE id = ?
        """, (name, serving_size, serving_unit, calories, protein, carbs, fat, food_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating food: {e}")

def get_food_by_id(conn, food_id):
    """Retrieve a single food row by id, or None if it doesn't exist."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM foods WHERE id = ?", (food_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Error retrieving food: {e}")
        return None

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
    """Seed the foods table with public data from a CSV file.

    Adds only the rows not already present (matched by name), so re-running
    after the CSV gains new entries backfills just those, without touching
    existing custom foods or duplicating rows already seeded."""
    try:
        cursor = conn.cursor()
        added = 0
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("SELECT 1 FROM foods WHERE name = ? AND source = 'public'", (row["name"],))
                if cursor.fetchone():
                    continue
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
                added += 1
        print(f"Seeded {added} new public food(s)." if added else "Public foods already up to date.")
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

def set_bodyweight(conn, date, weight_lbs):
    """Save (or update) the logged bodyweight for a given date."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bodyweight_logs (date, weight_lbs) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET weight_lbs = excluded.weight_lbs
        """, (date, weight_lbs))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving bodyweight: {e}")

def get_bodyweight(conn, date):
    """Retrieve the logged bodyweight for a given date, or None if not logged."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT weight_lbs FROM bodyweight_logs WHERE date = ?", (date,))
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        print(f"Error retrieving bodyweight: {e}")
        return None

def get_latest_bodyweight(conn):
    """Retrieve the most recently logged bodyweight (by date), or None if none logged."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT weight_lbs FROM bodyweight_logs ORDER BY date DESC, id DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error as e:
        print(f"Error retrieving latest bodyweight: {e}")
        return None

def set_user_profile(conn, gender, height_in, age):
    """Save (or update) the single saved user profile (gender, height, age)."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_profile (id, gender, height_in, age) VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                gender = excluded.gender, height_in = excluded.height_in, age = excluded.age
        """, (gender, height_in, age))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error saving user profile: {e}")

def get_user_profile(conn):
    """Retrieve the saved user profile as (gender, height_in, age), or None if not set."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT gender, height_in, age FROM user_profile WHERE id = 1")
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Error retrieving user profile: {e}")
        return None

def get_macro_totals_by_date_range(conn, start_date, end_date):
    """Sum calories/protein/carbs/fat per day for dates within [start_date, end_date]."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT le.date,
               SUM(f.calories * le.servings),
               SUM(f.protein * le.servings),
               SUM(f.carbs * le.servings),
               SUM(f.fat * le.servings)
        FROM log_entries le
        JOIN foods f ON le.food_id = f.id
        WHERE le.date BETWEEN ? AND ?
        GROUP BY le.date
        ORDER BY le.date
    """, (start_date, end_date))
    return cursor.fetchall()  # [(date, total_calories, total_protein, total_carbs, total_fat), ...]

def get_log_entries_by_date_range(conn, start_date, end_date):
    """Retrieve individual log entries (with computed macros) for dates within
    [start_date, end_date], for exporting to CSV."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT le.date, le.meal_type, f.name, le.servings,
               f.calories * le.servings, f.protein * le.servings,
               f.carbs * le.servings, f.fat * le.servings
        FROM log_entries le
        JOIN foods f ON le.food_id = f.id
        WHERE le.date BETWEEN ? AND ?
        ORDER BY le.date, le.meal_type
    """, (start_date, end_date))
    return cursor.fetchall()  # [(date, meal_type, food_name, servings, calories, protein, carbs, fat), ...]

def _compute_recipe_totals(conn, ingredients):
    """Sum calories/protein/carbs/fat for a list of (food_id, amount) ingredients,
    scaling each by amount / that food's native serving size."""
    totals = [0.0, 0.0, 0.0, 0.0]
    cursor = conn.cursor()
    for food_id, amount in ingredients:
        cursor.execute("SELECT serving_size, calories, protein, carbs, fat FROM foods WHERE id = ?", (food_id,))
        row = cursor.fetchone()
        if row is None:
            continue
        serving_size, calories, protein, carbs, fat = row
        servings = amount / serving_size if serving_size else 0
        totals[0] += calories * servings
        totals[1] += protein * servings
        totals[2] += carbs * servings
        totals[3] += fat * servings
    return tuple(totals)  # (calories, protein, carbs, fat)

def save_recipe(conn, name, ingredients, recipe_id=None):
    """Create or update a recipe from a list of (food_id, amount) ingredients.

    The recipe is represented as a single "virtual" food (1 serving = the whole
    batch) so it can be searched, logged, and shown in the Daily Log/Graphs tabs
    exactly like any other food. Editing a recipe updates that food's macros in
    place, so existing log entries for it reflect the recipe's current makeup."""
    calories, protein, carbs, fat = _compute_recipe_totals(conn, ingredients)
    try:
        cursor = conn.cursor()
        if recipe_id is None:
            food_id = add_food(conn, name, 1, "serving", calories, protein, carbs, fat, "recipe")
            cursor.execute("INSERT INTO recipes (name, food_id) VALUES (?, ?)", (name, food_id))
            recipe_id = cursor.lastrowid
        else:
            cursor.execute("SELECT food_id FROM recipes WHERE id = ?", (recipe_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"No recipe with id {recipe_id}")
            food_id = row[0]
            update_food(conn, food_id, name, 1, "serving", calories, protein, carbs, fat)
            cursor.execute("UPDATE recipes SET name = ? WHERE id = ?", (name, recipe_id))
            cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))

        cursor.executemany(
            "INSERT INTO recipe_ingredients (recipe_id, food_id, amount) VALUES (?, ?, ?)",
            [(recipe_id, food_id, amount) for food_id, amount in ingredients],
        )
        conn.commit()
        return recipe_id
    except sqlite3.Error as e:
        print(f"Error saving recipe: {e}")
        return None

def get_all_recipes(conn):
    """Retrieve all recipes as (recipe_id, name, food_id)."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, food_id FROM recipes ORDER BY name")
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error retrieving recipes: {e}")
        return []

def get_recipe_ingredients(conn, recipe_id):
    """Retrieve a recipe's ingredients as (food_id, food_name, amount, serving_size, serving_unit)."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.name, ri.amount, f.serving_size, f.serving_unit
            FROM recipe_ingredients ri
            JOIN foods f ON ri.food_id = f.id
            WHERE ri.recipe_id = ?
        """, (recipe_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error retrieving recipe ingredients: {e}")
        return []

