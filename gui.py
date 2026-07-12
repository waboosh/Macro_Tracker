import csv
import queue
import threading
import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from database import (
    add_food,
    add_log_entry,
    delete_log_entry,
    get_all_foods,
    get_all_recipes,
    get_bodyweight,
    get_daily_macro_totals,
    get_food_by_id,
    get_latest_bodyweight,
    get_log_entries_by_date,
    get_log_entries_by_date_range,
    get_macro_totals_by_date_range,
    get_recipe_ingredients,
    get_setting,
    get_user_profile,
    import_custom_foods,
    save_recipe,
    search_foods_by_name,
    set_bodyweight,
    set_setting,
    set_user_profile,
)
from fdc_client import FdcApiError, search_foods as search_usda_foods
from graphs import METRICS, build_metric_figure

FDC_API_KEY_SETTING = "fdc_api_key"

MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack"]


UNIT_LABELS = {"g": "Grams", "piece": "Pieces", "cup": "Cups", "slice": "Slices", "tbsp": "Tbsp"}


def label_for_unit(unit):
    """Human-friendly label for a food's native serving unit, e.g. 'cup' -> 'Cups'."""
    return UNIT_LABELS.get(unit.strip().lower(), unit.strip().capitalize())


def make_scrollable(parent):
    """Wrap a tab's content in a vertically scrollable area, so it stays usable even when
    it has more content than fits in the window (mouse wheel scrolls while hovered)."""
    canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(inner_id, width=e.width))
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def scroll(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", scroll))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    return inner


def build_add_entry_tab(parent, conn):
    """Search foods, pick one, and log it against a date/meal/servings."""
    parent = make_scrollable(parent)
    selected_food = {"id": None, "name": None, "serving_size": None, "serving_unit": None}

    search_frame = ttk.Frame(parent, padding=10)
    search_frame.pack(fill="x")

    ttk.Label(search_frame, text="Search food:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)

    columns = ("food", "serving", "calories", "protein", "carbs", "fat")
    results_tree = ttk.Treeview(parent, columns=columns, show="headings", height=8)
    results_tree.heading("food", text="Food")
    results_tree.heading("serving", text="Serving")
    results_tree.heading("calories", text="Calories")
    results_tree.heading("protein", text="Protein (g)")
    results_tree.heading("carbs", text="Carbs (g)")
    results_tree.heading("fat", text="Fat (g)")
    for col in ("serving", "calories", "protein", "carbs", "fat"):
        results_tree.column(col, width=90, anchor="e")
    results_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    results_by_id = {}  # food_id -> full row, keyed to survive re-searches

    online_frame = ttk.Frame(parent, padding=10)
    online_status_label = ttk.Label(online_frame, text="")
    online_status_label.pack(anchor="w")
    online_search_button = ttk.Button(online_frame, text="Search USDA Online")
    online_search_button.pack(anchor="w", pady=(2, 5))

    online_columns = ("food", "serving", "calories", "protein", "carbs", "fat")
    online_results_tree = ttk.Treeview(online_frame, columns=online_columns, show="headings", height=5)
    for col, text in zip(online_columns, ("Food", "Serving", "Calories", "Protein (g)", "Carbs (g)", "Fat (g)")):
        online_results_tree.heading(col, text=text)
    for col in ("serving", "calories", "protein", "carbs", "fat"):
        online_results_tree.column(col, width=90, anchor="e")
    online_results_tree.pack(fill="x")
    online_results_by_index = {}

    def run_search(*_):
        results_tree.delete(*results_tree.get_children())
        results_by_id.clear()
        online_frame.pack_forget()
        name = search_var.get().strip()
        if not name:
            return
        rows = search_foods_by_name(conn, name)
        for row in rows:
            food_id, food_name, serving_size, serving_unit, calories, protein, carbs, fat = row[:8]
            results_by_id[food_id] = row
            results_tree.insert(
                "",
                tk.END,
                iid=str(food_id),
                values=(
                    food_name,
                    f"{serving_size:g} {serving_unit}",
                    f"{calories:g}",
                    f"{protein:g}",
                    f"{carbs:g}",
                    f"{fat:g}",
                ),
            )
        if not rows:
            online_status_label.config(text=f"No local matches for '{name}'.")
            online_results_tree.delete(*online_results_tree.get_children())
            online_results_by_index.clear()
            online_frame.pack(fill="x", before=entry_frame)

    search_entry.bind("<Return>", run_search)
    search_var.trace_add("write", run_search)
    ttk.Button(search_frame, text="Search", command=run_search).pack(side="left")

    online_result_queue = queue.Queue()

    def search_online():
        api_key = get_setting(conn, FDC_API_KEY_SETTING)
        if not api_key:
            online_status_label.config(text="No USDA API key set. Add one in the Settings tab.")
            return
        name = search_var.get().strip()
        if not name:
            return

        online_status_label.config(text="Searching USDA FoodData Central...")
        online_search_button.config(state="disabled")

        def worker():
            try:
                online_result_queue.put((search_usda_foods(api_key, name), None))
            except FdcApiError as e:
                online_result_queue.put(([], str(e)))

        threading.Thread(target=worker, daemon=True).start()
        parent.after(100, poll_online_results)

    def poll_online_results():
        try:
            results, error = online_result_queue.get_nowait()
        except queue.Empty:
            parent.after(100, poll_online_results)
            return
        on_online_results(results, error)

    def on_online_results(results, error):
        online_search_button.config(state="normal")
        online_results_tree.delete(*online_results_tree.get_children())
        online_results_by_index.clear()
        if error:
            online_status_label.config(text=error)
            return
        if not results:
            online_status_label.config(text="No USDA results found.")
            return
        online_status_label.config(
            text=f"Found {len(results)} USDA result(s). Select one to add it to your food database."
        )
        for i, r in enumerate(results):
            online_results_by_index[i] = r
            online_results_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    r["name"],
                    f"{r['serving_size']:g} {r['serving_unit']}",
                    f"{r['calories']:g}",
                    f"{r['protein']:g}",
                    f"{r['carbs']:g}",
                    f"{r['fat']:g}",
                ),
            )

    online_search_button.config(command=search_online)

    def on_online_select(_event):
        selection = online_results_tree.selection()
        if not selection:
            return
        r = online_results_by_index[int(selection[0])]
        food_id = add_food(
            conn, r["name"], r["serving_size"], r["serving_unit"],
            r["calories"], r["protein"], r["carbs"], r["fat"], "usda",
        )
        selected_food["id"] = food_id
        selected_food["name"] = r["name"]
        selected_food["serving_size"] = r["serving_size"]
        selected_food["serving_unit"] = r["serving_unit"]
        selected_label.config(
            text=f"Selected food: {r['name']} ({r['serving_size']:g} {r['serving_unit']} per serving)"
        )
        amount_var.set("")
        servings_var.set("1")
        amount_label.config(text=f"{label_for_unit(r['serving_unit'])} eaten:")
        amount_entry.config(state="normal")
        online_status_label.config(text=f"Added '{r['name']}' to your food database and selected it.")

    online_results_tree.bind("<<TreeviewSelect>>", on_online_select)

    entry_frame = ttk.Frame(parent, padding=10)
    entry_frame.pack(fill="x")

    selected_label = ttk.Label(entry_frame, text="Selected food: none")
    selected_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    def on_select(_event):
        selection = results_tree.selection()
        if not selection:
            return
        row = results_by_id[int(selection[0])]
        selected_food["id"] = row[0]
        selected_food["name"] = row[1]
        selected_food["serving_size"] = row[2]
        selected_food["serving_unit"] = row[3]
        selected_label.config(text=f"Selected food: {row[1]} ({row[2]:g} {row[3]} per serving)")

        amount_var.set("")
        servings_var.set("1")
        amount_label.config(text=f"{label_for_unit(row[3])} eaten:")
        amount_entry.config(state="normal")

    results_tree.bind("<<TreeviewSelect>>", on_select)

    ttk.Label(entry_frame, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w")
    date_var = tk.StringVar(value=date.today().isoformat())
    date_entry = ttk.Entry(entry_frame, textvariable=date_var)
    date_entry.grid(row=1, column=1, sticky="ew", pady=2)

    ttk.Label(entry_frame, text="Meal:").grid(row=2, column=0, sticky="w")
    meal_var = tk.StringVar(value=MEAL_TYPES[0])
    meal_combo = ttk.Combobox(entry_frame, textvariable=meal_var, values=MEAL_TYPES, state="readonly")
    meal_combo.grid(row=2, column=1, sticky="ew", pady=2)

    amount_label = ttk.Label(entry_frame, text="Amount eaten:")
    amount_label.grid(row=3, column=0, sticky="w")
    amount_var = tk.StringVar()
    amount_entry = ttk.Entry(entry_frame, textvariable=amount_var, state="disabled")
    amount_entry.grid(row=3, column=1, sticky="ew", pady=2)

    ttk.Label(entry_frame, text="Servings:").grid(row=4, column=0, sticky="w")
    servings_var = tk.StringVar()
    servings_entry = ttk.Entry(entry_frame, textvariable=servings_var)
    servings_entry.grid(row=4, column=1, sticky="ew", pady=2)

    def on_amount_change(*_):
        amount_text = amount_var.get().strip()
        serving_size = selected_food.get("serving_size")
        if not amount_text or not serving_size:
            return
        try:
            amount = float(amount_text)
        except ValueError:
            return
        servings_var.set(f"{amount / serving_size:g}")

    amount_var.trace_add("write", on_amount_change)

    entry_frame.columnconfigure(1, weight=1)

    status_label = ttk.Label(entry_frame, text="")
    status_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def log_entry():
        if selected_food["id"] is None:
            status_label.config(text="Pick a food from the search results first.")
            return
        try:
            servings = float(servings_var.get())
        except ValueError:
            status_label.config(text="Servings must be a number.")
            return

        add_log_entry(conn, selected_food["id"], date_var.get(), meal_var.get(), servings)
        status_label.config(text=f"Logged {servings} serving(s) of {selected_food['name']}.")

    ttk.Button(entry_frame, text="Log Entry", command=log_entry).grid(
        row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0)
    )

    for widget in (date_entry, meal_combo, amount_entry, servings_entry):
        widget.bind("<Return>", lambda _event: log_entry())


def build_recipes_tab(parent, conn):
    """Build/edit a "recipe" (a fixed set of ingredients + amounts, e.g. a daily protein
    shake) and save it as a single loggable food. Saving computes the recipe's total
    macros from its ingredients and stores it as one food (1 serving = the whole batch),
    so it can be found via the food search in Add Entry and logged like anything else.
    Any ingredient typed in that isn't already in the food database gets added to it."""
    parent = make_scrollable(parent)
    recipe_frame = ttk.Frame(parent, padding=10)
    recipe_frame.pack(fill="x")

    current_recipe_id = {"id": None}
    pending_ingredients = []  # dicts: food_id, name, amount, serving_size, serving_unit
    selected_ingredient = {"food_id": None, "name": None, "serving_size": None, "serving_unit": None}

    top_row = ttk.Frame(recipe_frame)
    top_row.pack(fill="x")

    ttk.Label(top_row, text="Recipe name:").pack(side="left")
    recipe_name_var = tk.StringVar()
    ttk.Entry(top_row, textvariable=recipe_name_var, width=20).pack(side="left", padx=(5, 15))

    ttk.Label(top_row, text="Existing:").pack(side="left")
    recipe_select_var = tk.StringVar()
    recipe_combo = ttk.Combobox(top_row, textvariable=recipe_select_var, state="readonly", width=20)
    recipe_combo.pack(side="left", padx=5)

    recipes_by_name = {}  # name -> (recipe_id, food_id)

    def refresh_recipe_list():
        recipes_by_name.clear()
        for recipe_id, name, food_id in get_all_recipes(conn):
            recipes_by_name[name] = (recipe_id, food_id)
        recipe_combo.config(values=list(recipes_by_name.keys()))

    def new_recipe():
        current_recipe_id["id"] = None
        recipe_name_var.set("")
        recipe_select_var.set("")
        pending_ingredients.clear()
        refresh_pending_tree()
        recipe_status.config(text="")

    def edit_recipe(*_):
        name = recipe_select_var.get()
        if name not in recipes_by_name:
            return
        recipe_id, _food_id = recipes_by_name[name]
        current_recipe_id["id"] = recipe_id
        recipe_name_var.set(name)
        pending_ingredients.clear()
        for food_id, ing_name, amount, serving_size, serving_unit in get_recipe_ingredients(conn, recipe_id):
            pending_ingredients.append({
                "food_id": food_id,
                "name": ing_name,
                "amount": amount,
                "serving_size": serving_size,
                "serving_unit": serving_unit,
            })
        refresh_pending_tree()
        recipe_status.config(text=f"Editing '{name}'. Change ingredients/amounts below, then Save Recipe.")

    recipe_combo.bind("<<ComboboxSelected>>", edit_recipe)
    ttk.Button(top_row, text="New", command=new_recipe).pack(side="left", padx=(5, 0))

    ingredient_row = ttk.Frame(recipe_frame)
    ingredient_row.pack(fill="x", pady=(10, 0))

    ttk.Label(ingredient_row, text="Ingredient:").pack(side="left")
    ingredient_search_var = tk.StringVar()
    ingredient_search_entry = ttk.Entry(ingredient_row, textvariable=ingredient_search_var, width=20)
    ingredient_search_entry.pack(side="left", padx=5)

    ingredient_results_tree = ttk.Treeview(
        recipe_frame, columns=("food", "serving"), show="headings", height=3
    )
    ingredient_results_tree.heading("food", text="Food")
    ingredient_results_tree.heading("serving", text="Serving")
    ingredient_results_tree.column("serving", width=120, anchor="e")
    ingredient_results_by_id = {}

    new_ingredient_frame = ttk.LabelFrame(recipe_frame, text="Ingredient not found — add it", padding=8)
    new_food_specs = [
        ("Name", "name"),
        ("Serving Size", "serving_size"),
        ("Serving Unit", "serving_unit"),
        ("Calories", "calories"),
        ("Protein (g)", "protein"),
        ("Carbs (g)", "carbs"),
        ("Fat (g)", "fat"),
    ]
    new_food_fields = {}
    for i, (label, key) in enumerate(new_food_specs):
        row, col = divmod(i, 4)
        ttk.Label(new_ingredient_frame, text=f"{label}:").grid(row=row * 2, column=col, sticky="w", padx=2)
        var = tk.StringVar()
        ttk.Entry(new_ingredient_frame, textvariable=var, width=12).grid(
            row=row * 2 + 1, column=col, sticky="ew", padx=2, pady=(0, 5)
        )
        new_food_fields[key] = var
    for c in range(4):
        new_ingredient_frame.columnconfigure(c, weight=1)

    def search_ingredients(*_):
        ingredient_results_tree.delete(*ingredient_results_tree.get_children())
        ingredient_results_by_id.clear()
        new_ingredient_frame.pack_forget()
        name = ingredient_search_var.get().strip()
        if not name:
            return
        matches = search_foods_by_name(conn, name)
        for row in matches:
            food_id, food_name, serving_size, serving_unit = row[:4]
            ingredient_results_by_id[food_id] = row
            ingredient_results_tree.insert(
                "", tk.END, iid=str(food_id), values=(food_name, f"{serving_size:g} {serving_unit}")
            )
        if not matches:
            new_food_fields["name"].set(name)
            new_ingredient_frame.pack(fill="x", pady=(5, 0))

    def on_ingredient_select(_event):
        selection = ingredient_results_tree.selection()
        if not selection:
            return
        row = ingredient_results_by_id[int(selection[0])]
        selected_ingredient["food_id"] = row[0]
        selected_ingredient["name"] = row[1]
        selected_ingredient["serving_size"] = row[2]
        selected_ingredient["serving_unit"] = row[3]
        amount_unit_label.config(text=f"Amount ({label_for_unit(row[3])}):")
        new_ingredient_frame.pack_forget()

    ingredient_results_tree.bind("<<TreeviewSelect>>", on_ingredient_select)
    ingredient_search_entry.bind("<Return>", search_ingredients)
    ingredient_search_var.trace_add("write", search_ingredients)
    ttk.Button(ingredient_row, text="Search", command=search_ingredients).pack(side="left")
    ingredient_results_tree.pack(fill="x", pady=(5, 0))

    def add_new_ingredient():
        name = new_food_fields["name"].get().strip()
        serving_unit = new_food_fields["serving_unit"].get().strip()
        try:
            serving_size = float(new_food_fields["serving_size"].get())
            calories = float(new_food_fields["calories"].get())
            protein = float(new_food_fields["protein"].get())
            carbs = float(new_food_fields["carbs"].get())
            fat = float(new_food_fields["fat"].get())
        except ValueError:
            recipe_status.config(text="New ingredient: serving size/calories/protein/carbs/fat must be numbers.")
            return
        if not name or not serving_unit:
            recipe_status.config(text="New ingredient: name and serving unit are required.")
            return

        food_id = add_food(conn, name, serving_size, serving_unit, calories, protein, carbs, fat, "custom")
        selected_ingredient["food_id"] = food_id
        selected_ingredient["name"] = name
        selected_ingredient["serving_size"] = serving_size
        selected_ingredient["serving_unit"] = serving_unit
        amount_unit_label.config(text=f"Amount ({label_for_unit(serving_unit)}):")
        for var in new_food_fields.values():
            var.set("")
        new_ingredient_frame.pack_forget()
        recipe_status.config(text=f"Added '{name}' to the food database. Set an amount and click Add Ingredient.")

    ttk.Button(new_ingredient_frame, text="Add & Use as Ingredient", command=add_new_ingredient).grid(
        row=4, column=0, columnspan=4, sticky="ew", pady=(5, 0)
    )

    amount_row = ttk.Frame(recipe_frame)
    amount_row.pack(fill="x", pady=(8, 0))
    amount_unit_label = ttk.Label(amount_row, text="Amount:")
    amount_unit_label.pack(side="left")
    ingredient_amount_var = tk.StringVar()
    ttk.Entry(amount_row, textvariable=ingredient_amount_var, width=10).pack(side="left", padx=5)

    pending_tree = None  # forward reference, assigned below

    def refresh_pending_tree():
        pending_tree.delete(*pending_tree.get_children())
        total_cal = total_pro = total_carb = total_fat = 0.0
        for i, ing in enumerate(pending_ingredients):
            food = get_food_by_id(conn, ing["food_id"])
            if food is None:
                continue
            _, _, serving_size, _serving_unit, calories, protein, carbs, fat, _source = food
            servings = ing["amount"] / serving_size if serving_size else 0
            cal, pro, carb, fatg = calories * servings, protein * servings, carbs * servings, fat * servings
            total_cal += cal
            total_pro += pro
            total_carb += carb
            total_fat += fatg
            pending_tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    ing["name"],
                    f"{ing['amount']:g} {ing['serving_unit']}",
                    f"{cal:.0f}",
                    f"{pro:.1f}",
                    f"{carb:.1f}",
                    f"{fatg:.1f}",
                ),
            )
        totals_label.config(
            text=f"Recipe totals (1 batch = 1 serving when logged): {total_cal:.0f} kcal, "
            f"{total_pro:.1f}g protein, {total_carb:.1f}g carbs, {total_fat:.1f}g fat"
        )

    def add_ingredient_to_recipe():
        if selected_ingredient["food_id"] is None:
            recipe_status.config(text="Search for and select an ingredient first.")
            return
        try:
            amount = float(ingredient_amount_var.get())
        except ValueError:
            recipe_status.config(text="Amount must be a number.")
            return
        if amount <= 0:
            recipe_status.config(text="Amount must be positive.")
            return

        pending_ingredients.append({
            "food_id": selected_ingredient["food_id"],
            "name": selected_ingredient["name"],
            "amount": amount,
            "serving_size": selected_ingredient["serving_size"],
            "serving_unit": selected_ingredient["serving_unit"],
        })
        refresh_pending_tree()
        ingredient_search_var.set("")
        ingredient_amount_var.set("")
        selected_ingredient.update(food_id=None, name=None, serving_size=None, serving_unit=None)
        ingredient_results_tree.delete(*ingredient_results_tree.get_children())
        recipe_status.config(text="")

    ttk.Button(amount_row, text="Add Ingredient", command=add_ingredient_to_recipe).pack(side="left", padx=(5, 0))

    pending_columns = ("ingredient", "amount", "calories", "protein", "carbs", "fat")
    pending_tree = ttk.Treeview(recipe_frame, columns=pending_columns, show="headings", height=4)
    pending_headings = {
        "ingredient": "Ingredient",
        "amount": "Amount",
        "calories": "Calories",
        "protein": "Protein (g)",
        "carbs": "Carbs (g)",
        "fat": "Fat (g)",
    }
    for col, text in pending_headings.items():
        pending_tree.heading(col, text=text)
    for col in ("amount", "calories", "protein", "carbs", "fat"):
        pending_tree.column(col, width=80, anchor="e")
    pending_tree.pack(fill="x", pady=(10, 0))

    totals_label = ttk.Label(recipe_frame, text="")
    totals_label.pack(anchor="w", pady=(5, 0))

    def remove_selected_ingredient():
        selection = pending_tree.selection()
        if not selection:
            return
        for iid in sorted((int(i) for i in selection), reverse=True):
            del pending_ingredients[iid]
        refresh_pending_tree()

    ttk.Button(recipe_frame, text="Remove Selected Ingredient", command=remove_selected_ingredient).pack(
        fill="x", pady=(5, 0)
    )

    recipe_status = ttk.Label(recipe_frame, text="")
    recipe_status.pack(anchor="w", pady=(8, 0))

    def save_recipe_clicked():
        name = recipe_name_var.get().strip()
        if not name:
            recipe_status.config(text="Enter a recipe name.")
            return
        if not pending_ingredients:
            recipe_status.config(text="Add at least one ingredient.")
            return

        ingredients = [(ing["food_id"], ing["amount"]) for ing in pending_ingredients]
        new_recipe_id = save_recipe(conn, name, ingredients, recipe_id=current_recipe_id["id"])
        if new_recipe_id is None:
            recipe_status.config(text="Could not save recipe (name may already be in use).")
            return

        current_recipe_id["id"] = new_recipe_id
        refresh_recipe_list()
        recipe_select_var.set(name)
        recipe_status.config(text=f"Saved '{name}'. Search for it in Add Entry to log it.")

    ttk.Button(recipe_frame, text="Save Recipe", command=save_recipe_clicked).pack(fill="x", pady=(5, 0))

    refresh_recipe_list()
    return refresh_recipe_list


def build_daily_log_tab(parent, conn):
    """View logged entries for a date, delete them, and see the day's totals."""
    controls_frame = ttk.Frame(parent, padding=10)
    controls_frame.pack(fill="x")

    ttk.Label(controls_frame, text="Date (YYYY-MM-DD):").pack(side="left")
    date_var = tk.StringVar(value=date.today().isoformat())
    date_entry = ttk.Entry(controls_frame, textvariable=date_var)
    date_entry.pack(side="left", fill="x", expand=True, padx=5)

    columns = ("food", "meal", "servings")
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
    tree.heading("food", text="Food")
    tree.heading("meal", text="Meal")
    tree.heading("servings", text="Servings")
    tree.column("servings", width=80, anchor="e")
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    totals_label = ttk.Label(parent, text="")
    totals_label.pack(fill="x", padx=10, pady=(0, 10))

    def refresh(*_):
        tree.delete(*tree.get_children())
        for entry_id, food_name, _entry_date, meal_type, servings in get_log_entries_by_date(conn, date_var.get()):
            tree.insert("", tk.END, iid=str(entry_id), values=(food_name, meal_type, servings))

        calories, protein, carbs, fat = get_daily_macro_totals(conn, date_var.get())
        totals_label.config(
            text=(
                f"Totals: {calories or 0:.0f} kcal, "
                f"{protein or 0:.1f}g protein, {carbs or 0:.1f}g carbs, {fat or 0:.1f}g fat"
            )
        )

    def delete_selected():
        selection = tree.selection()
        if not selection:
            return
        for entry_id in selection:
            delete_log_entry(conn, int(entry_id))
        refresh()

    ttk.Button(controls_frame, text="Load", command=refresh).pack(side="left")
    ttk.Button(parent, text="Delete Selected", command=delete_selected).pack(fill="x", padx=10, pady=(0, 10))
    date_entry.bind("<Return>", refresh)

    export_frame = ttk.LabelFrame(parent, text="Export to CSV", padding=10)
    export_frame.pack(fill="x", padx=10, pady=(0, 10))

    ttk.Label(export_frame, text="Start date:").pack(side="left")
    export_start_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(export_frame, textvariable=export_start_var, width=12).pack(side="left", padx=5)

    ttk.Label(export_frame, text="End date:").pack(side="left")
    export_end_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(export_frame, textvariable=export_end_var, width=12).pack(side="left", padx=5)

    export_status = ttk.Label(export_frame, text="")
    export_status.pack(side="left", padx=(10, 0))

    def export_csv():
        rows = get_log_entries_by_date_range(conn, export_start_var.get(), export_end_var.get())
        if not rows:
            export_status.config(text="No log entries in that date range.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="macro_log_export.csv",
        )
        if not path:
            return

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "meal", "food", "servings", "calories", "protein_g", "carbs_g", "fat_g"])

            current_date = rows[0][0]
            day_totals = [0.0, 0.0, 0.0, 0.0]
            for row_date, meal_type, food_name, servings, calories, protein, carbs, fat in rows:
                if row_date != current_date:
                    writer.writerow([current_date, "", "TOTAL", "", *(f"{v:.1f}" for v in day_totals)])
                    day_totals = [0.0, 0.0, 0.0, 0.0]
                    current_date = row_date
                writer.writerow([
                    row_date, meal_type, food_name, f"{servings:g}",
                    f"{calories:.1f}", f"{protein:.1f}", f"{carbs:.1f}", f"{fat:.1f}",
                ])
                day_totals[0] += calories
                day_totals[1] += protein
                day_totals[2] += carbs
                day_totals[3] += fat
            writer.writerow([current_date, "", "TOTAL", "", *(f"{v:.1f}" for v in day_totals)])

        export_status.config(text=f"Exported {len(rows)} entries to {path}")

    ttk.Button(export_frame, text="Export CSV...", command=export_csv).pack(side="left", padx=(10, 0))

    refresh()
    return refresh


def build_graphs_tab(parent, conn):
    """Chart daily calories and/or macros over a date range, one metric at a time or combined."""
    controls_frame = ttk.Frame(parent, padding=10)
    controls_frame.pack(fill="x")

    ttk.Label(controls_frame, text="Start date:").pack(side="left")
    start_var = tk.StringVar(value=(date.today() - timedelta(days=6)).isoformat())
    start_entry = ttk.Entry(controls_frame, textvariable=start_var, width=12)
    start_entry.pack(side="left", padx=5)

    ttk.Label(controls_frame, text="End date:").pack(side="left")
    end_var = tk.StringVar(value=date.today().isoformat())
    end_entry = ttk.Entry(controls_frame, textvariable=end_var, width=12)
    end_entry.pack(side="left", padx=5)

    metrics_frame = ttk.Frame(parent, padding=(10, 0))
    metrics_frame.pack(fill="x")

    metric_vars = {}
    for key, info in METRICS.items():
        var = tk.BooleanVar(value=(key == "calories"))
        metric_vars[key] = var
        ttk.Checkbutton(metrics_frame, text=info["label"], variable=var, command=lambda: load_chart()).pack(
            side="left", padx=(0, 10)
        )

    chart_frame = ttk.Frame(parent)
    chart_frame.pack(fill="both", expand=True, padx=10, pady=(10, 0))

    status_label = ttk.Label(parent, text="")
    status_label.pack(fill="x", padx=10, pady=(0, 10))

    canvas_holder = {"canvas": None}

    def load_chart(*_):
        if canvas_holder["canvas"] is not None:
            canvas_holder["canvas"].get_tk_widget().destroy()
            canvas_holder["canvas"] = None

        selected_metrics = [key for key, var in metric_vars.items() if var.get()]
        if not selected_metrics:
            status_label.config(text="Select at least one metric to display.")
            return

        rows = get_macro_totals_by_date_range(conn, start_var.get(), end_var.get())
        if not rows:
            status_label.config(text="No log entries in that date range.")
            return

        status_label.config(text="")
        figure = build_metric_figure(rows, selected_metrics)
        canvas = FigureCanvasTkAgg(figure, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas_holder["canvas"] = canvas

    ttk.Button(controls_frame, text="Load Graph", command=load_chart).pack(side="left", padx=5)
    start_entry.bind("<Return>", load_chart)
    end_entry.bind("<Return>", load_chart)

    load_chart()


def build_food_database_tab(parent, conn):
    """Browse/search all foods, add custom ones, and import a custom CSV."""
    search_frame = ttk.Frame(parent, padding=10)
    search_frame.pack(fill="x")

    ttk.Label(search_frame, text="Search food:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var)
    search_entry.pack(side="left", fill="x", expand=True, padx=5)

    columns = ("food", "serving", "calories", "protein", "carbs", "fat", "source")
    columns_without_source = ("food", "serving", "calories", "protein", "carbs", "fat")

    tree_frame = ttk.Frame(parent)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
    headings = {
        "food": "Food",
        "serving": "Serving",
        "calories": "Calories",
        "protein": "Protein (g)",
        "carbs": "Carbs (g)",
        "fat": "Fat (g)",
        "source": "Source",
    }
    for col, text in headings.items():
        tree.heading(col, text=text)
    for col in ("serving", "calories", "protein", "carbs", "fat", "source"):
        tree.column(col, width=85, anchor="e" if col != "source" else "center", stretch=False)
    tree["displaycolumns"] = columns_without_source

    tree_hscroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(xscrollcommand=tree_hscroll.set)
    tree.pack(side="top", fill="both", expand=True)
    tree_hscroll.pack(side="bottom", fill="x")

    def populate(rows):
        tree.delete(*tree.get_children())
        for food_id, food_name, serving_size, serving_unit, calories, protein, carbs, fat, source in rows:
            tree.insert(
                "",
                tk.END,
                iid=str(food_id),
                values=(
                    food_name,
                    f"{serving_size:g} {serving_unit}",
                    f"{calories:g}",
                    f"{protein:g}",
                    f"{carbs:g}",
                    f"{fat:g}",
                    source or "",
                ),
            )

    def refresh(*_):
        name = search_var.get().strip()
        populate(search_foods_by_name(conn, name) if name else get_all_foods(conn))

    search_entry.bind("<Return>", refresh)
    search_var.trace_add("write", refresh)
    ttk.Button(search_frame, text="Search", command=refresh).pack(side="left")

    def show_all():
        search_var.set("")
        refresh()

    ttk.Button(search_frame, text="Show All", command=show_all).pack(side="left", padx=(5, 0))

    source_column_visible = {"value": False}

    def toggle_source_column():
        source_column_visible["value"] = not source_column_visible["value"]
        tree["displaycolumns"] = columns if source_column_visible["value"] else columns_without_source

    ttk.Button(search_frame, text="Source", command=toggle_source_column).pack(side="left", padx=(5, 0))

    add_frame = ttk.LabelFrame(parent, text="Add Custom Food", padding=10)
    add_frame.pack(fill="x", padx=10, pady=(0, 10))

    field_specs = [
        ("Name", "name"),
        ("Serving Size", "serving_size"),
        ("Serving Unit", "serving_unit"),
        ("Calories", "calories"),
        ("Protein (g)", "protein"),
        ("Carbs (g)", "carbs"),
        ("Fat (g)", "fat"),
    ]
    fields = {}
    field_entries = []
    for i, (label, key) in enumerate(field_specs):
        row, col = divmod(i, 4)
        ttk.Label(add_frame, text=f"{label}:").grid(row=row * 2, column=col, sticky="w", padx=2)
        var = tk.StringVar()
        entry = ttk.Entry(add_frame, textvariable=var, width=14)
        entry.grid(row=row * 2 + 1, column=col, sticky="ew", padx=2, pady=(0, 5))
        fields[key] = var
        field_entries.append(entry)
    for c in range(4):
        add_frame.columnconfigure(c, weight=1)

    add_status = ttk.Label(add_frame, text="")
    add_status.grid(row=4, column=0, columnspan=4, sticky="w")

    def add_food_clicked():
        name = fields["name"].get().strip()
        serving_unit = fields["serving_unit"].get().strip()
        try:
            serving_size = float(fields["serving_size"].get())
            calories = float(fields["calories"].get())
            protein = float(fields["protein"].get())
            carbs = float(fields["carbs"].get())
            fat = float(fields["fat"].get())
        except ValueError:
            add_status.config(text="Serving size, calories, protein, carbs, and fat must be numbers.")
            return
        if not name or not serving_unit:
            add_status.config(text="Name and serving unit are required.")
            return

        add_food(conn, name, serving_size, serving_unit, calories, protein, carbs, fat, "custom")
        add_status.config(text=f"Added {name}.")
        for var in fields.values():
            var.set("")
        refresh()

    ttk.Button(add_frame, text="Add Food", command=add_food_clicked).grid(
        row=5, column=0, columnspan=4, sticky="ew", pady=(5, 0)
    )
    for entry in field_entries:
        entry.bind("<Return>", lambda _event: add_food_clicked())

    def import_csv():
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        success_count, errors = import_custom_foods(conn, path)
        message = f"Imported {success_count} food(s)."
        if errors:
            message += f" {len(errors)} row(s) skipped."
        messagebox.showinfo("Import Custom Foods", message)
        refresh()

    ttk.Button(parent, text="Import Custom Foods CSV...", command=import_csv).pack(
        fill="x", padx=10, pady=(0, 10)
    )

    refresh()
    return refresh


PROTEIN_PER_LB = 0.7

CALORIES_PER_LB = 3500

ACTIVITY_LEVELS = {
    "Sedentary (little/no exercise)": 1.2,
    "Light (exercise 1-3 days/week)": 1.375,
    "Moderate (exercise 3-5 days/week)": 1.55,
    "Active (exercise 6-7 days/week)": 1.725,
    "Very Active (hard exercise/physical job)": 1.9,
}


def calculate_bmr(weight_lbs, height_in, age, gender):
    """Estimate Basal Metabolic Rate using the Mifflin-St Jeor equation."""
    weight_kg = weight_lbs * 0.453592
    height_cm = height_in * 2.54
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if gender == "Male" else base - 161


def build_tracking_tab(parent, conn):
    """Log bodyweight/profile, see minimum protein target vs. logged protein, and estimate
    daily calorie targets for gaining, maintaining, or losing weight."""
    parent = make_scrollable(parent)
    top_info_frame = ttk.Frame(parent)
    top_info_frame.pack(fill="x", padx=10, pady=(10, 0))

    current_bw_label = ttk.Label(top_info_frame, text="", anchor="e")
    current_bw_label.pack(side="top", fill="x")
    current_profile_label = ttk.Label(top_info_frame, text="", anchor="e")
    current_profile_label.pack(side="top", fill="x")
    current_protein_target_label = ttk.Label(top_info_frame, text="", anchor="e")
    current_protein_target_label.pack(side="top", fill="x")

    def refresh_current_info():
        latest_weight = get_latest_bodyweight(conn)
        current_bw_label.config(
            text=f"Current saved bodyweight: {latest_weight:g} lbs" if latest_weight is not None
            else "Current saved bodyweight: not set"
        )
        profile = get_user_profile(conn)
        if profile is None:
            current_profile_label.config(text="Current saved profile: not set")
        else:
            gender, height_in, age, _protein_per_lb = profile
            ft, inches = divmod(height_in, 12)
            current_profile_label.config(
                text=f"Current saved profile: {gender}, {int(ft)}'{inches:g}\", {int(age)} yrs"
            )

        if latest_weight is not None and profile is not None:
            protein_per_lb = profile[3]
            target_protein = protein_per_lb * latest_weight
            current_protein_target_label.config(
                text=f"Target protein: {target_protein:.1f} g ({protein_per_lb:g} g/lb x {latest_weight:g} lbs)"
            )
        else:
            current_protein_target_label.config(text="Target protein: not set")

    controls_frame = ttk.Frame(parent, padding=10)
    controls_frame.pack(fill="x")

    ttk.Label(controls_frame, text="Date (YYYY-MM-DD):").pack(side="left")
    date_var = tk.StringVar(value=date.today().isoformat())
    date_entry = ttk.Entry(controls_frame, textvariable=date_var, width=12)
    date_entry.pack(side="left", padx=5)

    weight_frame = ttk.Frame(parent, padding=10)
    weight_frame.pack(fill="x")

    ttk.Label(weight_frame, text="Bodyweight (lbs):").pack(side="left")
    weight_var = tk.StringVar()
    weight_entry = ttk.Entry(weight_frame, textvariable=weight_var, width=12)
    weight_entry.pack(side="left", padx=5)

    status_label = ttk.Label(parent, text="")
    status_label.pack(fill="x", padx=10)

    profile_frame = ttk.LabelFrame(parent, text="Profile", padding=10)
    profile_frame.pack(fill="x", padx=10, pady=(10, 0))

    ttk.Label(profile_frame, text="Gender:").grid(row=0, column=0, sticky="w")
    gender_var = tk.StringVar(value="Male")
    ttk.Combobox(
        profile_frame, textvariable=gender_var, values=["Male", "Female"], state="readonly", width=8
    ).grid(row=0, column=1, sticky="w", padx=(2, 15))

    ttk.Label(profile_frame, text="Height:").grid(row=0, column=2, sticky="w")
    height_ft_var = tk.StringVar()
    height_ft_entry = ttk.Entry(profile_frame, textvariable=height_ft_var, width=3)
    height_ft_entry.grid(row=0, column=3, sticky="w", padx=(2, 2))
    ttk.Label(profile_frame, text="ft").grid(row=0, column=4, sticky="w")
    height_in_var = tk.StringVar()
    height_in_entry = ttk.Entry(profile_frame, textvariable=height_in_var, width=3)
    height_in_entry.grid(row=0, column=5, sticky="w", padx=(8, 2))
    ttk.Label(profile_frame, text="in").grid(row=0, column=6, sticky="w", padx=(0, 15))

    ttk.Label(profile_frame, text="Age:").grid(row=0, column=7, sticky="w")
    age_var = tk.StringVar()
    age_entry = ttk.Entry(profile_frame, textvariable=age_var, width=6)
    age_entry.grid(row=0, column=8, sticky="w", padx=(2, 15))

    ttk.Label(profile_frame, text="Protein target (g/lb bodyweight):").grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(8, 0)
    )
    protein_target_var = tk.StringVar(value=f"{PROTEIN_PER_LB:g}")
    protein_target_entry = ttk.Entry(profile_frame, textvariable=protein_target_var, width=6)
    protein_target_entry.grid(row=1, column=3, sticky="w", pady=(8, 0))

    profile_status = ttk.Label(profile_frame, text="")
    profile_status.grid(row=2, column=0, columnspan=9, sticky="w", pady=(8, 0))

    def save_profile():
        try:
            height_ft = float(height_ft_var.get() or 0)
            height_in_extra = float(height_in_var.get() or 0)
            age = int(age_var.get())
            protein_per_lb = float(protein_target_var.get())
        except ValueError:
            profile_status.config(text="Height, age, and protein target must be numbers.")
            return
        height_in = height_ft * 12 + height_in_extra
        if height_in <= 0 or age <= 0 or protein_per_lb <= 0:
            profile_status.config(text="Height, age, and protein target must be positive.")
            return

        set_user_profile(conn, gender_var.get(), height_in, age, protein_per_lb)
        profile_status.config(text="Profile saved.")
        refresh_current_info()
        update_results()

    ttk.Button(profile_frame, text="Save Profile", command=save_profile).grid(
        row=0, column=9, sticky="ew"
    )
    for widget in (height_ft_entry, height_in_entry, age_entry, protein_target_entry):
        widget.bind("<Return>", lambda _event: save_profile())

    def load_profile():
        profile = get_user_profile(conn)
        if profile is None:
            return
        gender, height_in, age, protein_per_lb = profile
        ft, inches = divmod(height_in, 12)
        gender_var.set(gender)
        height_ft_var.set(str(int(ft)))
        height_in_var.set(f"{inches:g}")
        age_var.set(str(int(age)))
        protein_target_var.set(f"{protein_per_lb:g}")

    results_frame = ttk.Frame(parent, padding=10)
    results_frame.pack(fill="x")

    min_protein_label = ttk.Label(results_frame, text="")
    min_protein_label.pack(anchor="w", pady=(0, 5))

    logged_protein_label = ttk.Label(results_frame, text="")
    logged_protein_label.pack(anchor="w")

    progress_var = tk.DoubleVar(value=0)
    progress_bar = ttk.Progressbar(
        results_frame, orient="horizontal", length=300, mode="determinate", maximum=100, variable=progress_var
    )
    progress_bar.pack(anchor="w", fill="x", pady=(8, 0))

    def update_results():
        weight_text = weight_var.get().strip()
        if not weight_text:
            min_protein_label.config(text="Enter a bodyweight to calculate your minimum protein intake.")
            logged_protein_label.config(text="")
            progress_var.set(0)
            return
        try:
            weight = float(weight_text)
        except ValueError:
            min_protein_label.config(text="")
            logged_protein_label.config(text="")
            progress_var.set(0)
            return

        try:
            protein_per_lb = float(protein_target_var.get())
        except ValueError:
            protein_per_lb = PROTEIN_PER_LB

        min_protein = protein_per_lb * weight
        min_protein_label.config(
            text=f"Minimum protein intake ({protein_per_lb:g} x {weight:g} lbs): {min_protein:.1f} g"
        )

        _, protein, _, _ = get_daily_macro_totals(conn, date_var.get())
        protein = protein or 0
        pct = (protein / min_protein * 100) if min_protein > 0 else 0
        logged_protein_label.config(
            text=f"Protein logged for {date_var.get()}: {protein:.1f} g ({pct:.0f}% of minimum)"
        )
        progress_var.set(min(max(pct, 0), 100))

    def load(*_):
        weight = get_bodyweight(conn, date_var.get())
        if weight is None:
            weight = get_latest_bodyweight(conn)
        weight_var.set(f"{weight:g}" if weight is not None else "")
        status_label.config(text="")
        update_results()
        refresh_current_info()

    def save_weight():
        try:
            weight = float(weight_var.get())
        except ValueError:
            status_label.config(text="Bodyweight must be a number.")
            return
        if weight <= 0:
            status_label.config(text="Bodyweight must be positive.")
            return

        set_bodyweight(conn, date_var.get(), weight)
        status_label.config(text=f"Saved bodyweight for {date_var.get()}.")
        update_results()
        refresh_current_info()

    ttk.Button(controls_frame, text="Load", command=load).pack(side="left")
    ttk.Button(weight_frame, text="Save Weight", command=save_weight).pack(side="left")
    date_entry.bind("<Return>", load)
    weight_entry.bind("<Return>", lambda _event: save_weight())

    calorie_frame = ttk.LabelFrame(parent, text="Calorie Tracking", padding=10)
    calorie_frame.pack(fill="x", padx=10, pady=(10, 0))

    ttk.Label(calorie_frame, text="Activity level:").grid(row=0, column=0, sticky="w")
    activity_var = tk.StringVar(value=list(ACTIVITY_LEVELS.keys())[2])
    ttk.Combobox(
        calorie_frame, textvariable=activity_var, values=list(ACTIVITY_LEVELS.keys()), state="readonly", width=34
    ).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(5, 0), pady=2)

    ttk.Label(calorie_frame, text="Target rate (lbs/week):").grid(row=1, column=0, sticky="w")
    rate_var = tk.StringVar(value="0.5")
    ttk.Entry(calorie_frame, textvariable=rate_var, width=8).grid(
        row=1, column=1, sticky="w", padx=(5, 0), pady=2
    )

    calorie_result_label = ttk.Label(calorie_frame, text="", wraplength=650, justify="left")
    calories_eaten_label = ttk.Label(calorie_frame, text="", wraplength=650, justify="left")

    calorie_progress_var = tk.DoubleVar(value=0)
    calorie_progress_bar = ttk.Progressbar(
        calorie_frame, orient="horizontal", length=300, mode="determinate", maximum=100,
        variable=calorie_progress_var,
    )

    def compute_calories(mode):
        profile = get_user_profile(conn)
        if profile is None:
            calorie_result_label.config(text="Fill in and save your profile (gender, height, age) first.")
            calories_eaten_label.config(text="")
            calorie_progress_var.set(0)
            return
        gender, height_in, age, _protein_per_lb = profile

        weight_text = weight_var.get().strip()
        if not weight_text:
            calorie_result_label.config(text="Enter/load a bodyweight first.")
            calories_eaten_label.config(text="")
            calorie_progress_var.set(0)
            return
        try:
            weight = float(weight_text)
        except ValueError:
            calorie_result_label.config(text="Bodyweight must be a number.")
            calories_eaten_label.config(text="")
            calorie_progress_var.set(0)
            return

        bmr = calculate_bmr(weight, height_in, age, gender)
        maintenance = bmr * ACTIVITY_LEVELS[activity_var.get()]

        rate = None
        if mode != "maintain":
            try:
                rate = float(rate_var.get())
            except ValueError:
                calorie_result_label.config(text="Target rate must be a number.")
                calories_eaten_label.config(text="")
                calorie_progress_var.set(0)
                return
            if rate <= 0:
                calorie_result_label.config(text="Target rate must be positive.")
                calories_eaten_label.config(text="")
                calorie_progress_var.set(0)
                return

        if mode == "maintain":
            target_calories = maintenance
            calorie_result_label.config(text=f"Maintenance calories: {maintenance:.0f} kcal/day.")
        elif mode == "gain":
            daily_adjustment = rate * CALORIES_PER_LB / 7
            target_calories = maintenance + daily_adjustment
            calorie_result_label.config(
                text=f"To gain {rate:g} lb/week: {target_calories:.0f} kcal/day "
                f"(maintenance {maintenance:.0f} + {daily_adjustment:.0f})."
            )
        else:
            daily_adjustment = rate * CALORIES_PER_LB / 7
            target_calories = maintenance - daily_adjustment
            calorie_result_label.config(
                text=f"To lose {rate:g} lb/week: {target_calories:.0f} kcal/day "
                f"(maintenance {maintenance:.0f} - {daily_adjustment:.0f})."
            )

        calories_eaten, _, _, _ = get_daily_macro_totals(conn, date_var.get())
        calories_eaten = calories_eaten or 0
        pct = (calories_eaten / target_calories * 100) if target_calories > 0 else 0
        calories_eaten_label.config(
            text=f"Calories eaten for {date_var.get()}: {calories_eaten:.0f} kcal "
            f"({pct:.0f}% of {mode} target of {target_calories:.0f} kcal)"
        )
        calorie_progress_var.set(min(max(pct, 0), 100))

    button_frame = ttk.Frame(calorie_frame)
    button_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
    ttk.Button(button_frame, text="Gain Weight", command=lambda: compute_calories("gain")).pack(
        side="left", padx=(0, 5)
    )
    ttk.Button(button_frame, text="Maintain Weight", command=lambda: compute_calories("maintain")).pack(
        side="left", padx=(0, 5)
    )
    ttk.Button(button_frame, text="Lose Weight", command=lambda: compute_calories("lose")).pack(side="left")

    calorie_result_label.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
    calories_eaten_label.grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))
    calorie_progress_bar.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 0))

    for c in range(4):
        calorie_frame.columnconfigure(c, weight=1)

    load_profile()
    refresh_current_info()
    load()
    return load


def build_settings_tab(parent, conn):
    """Configure the USDA FoodData Central API key used as a fallback food search when
    a food isn't found locally (Add Entry tab)."""
    frame = ttk.LabelFrame(parent, text="USDA FoodData Central", padding=10)
    frame.pack(fill="x", padx=10, pady=10)

    ttk.Label(
        frame,
        text=(
            "Used in Add Entry to search USDA's food database when a food isn't found locally.\n"
            "Get a free API key at fdc.nal.usda.gov/api-key-signup.html, then paste it below."
        ),
        justify="left",
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

    ttk.Label(frame, text="API key:").grid(row=1, column=0, sticky="w")
    api_key_var = tk.StringVar(value=get_setting(conn, FDC_API_KEY_SETTING, "") or "")
    api_key_entry = ttk.Entry(frame, textvariable=api_key_var, width=40, show="*")
    api_key_entry.grid(row=1, column=1, sticky="ew", padx=(5, 5))

    show_key_var = tk.BooleanVar(value=False)

    def toggle_show_key():
        api_key_entry.config(show="" if show_key_var.get() else "*")

    ttk.Checkbutton(frame, text="Show", variable=show_key_var, command=toggle_show_key).grid(
        row=1, column=2, sticky="w"
    )

    status_label = ttk.Label(frame, text="")
    status_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def save_key():
        set_setting(conn, FDC_API_KEY_SETTING, api_key_var.get().strip())
        status_label.config(text="API key saved.")

    ttk.Button(frame, text="Save", command=save_key).grid(row=3, column=0, sticky="w", pady=(8, 0))
    api_key_entry.bind("<Return>", lambda _event: save_key())

    frame.columnconfigure(1, weight=1)


def main(conn):
    root = tk.Tk()
    root.title("Macro Tracker")
    root.geometry("800x600")

    notebook = ttk.Notebook(root)

    add_entry_tab = ttk.Frame(notebook)
    database_tab = ttk.Frame(notebook)
    recipes_tab = ttk.Frame(notebook)
    log_tab = ttk.Frame(notebook)
    graphs_tab = ttk.Frame(notebook)
    tracking_tab = ttk.Frame(notebook)
    settings_tab = ttk.Frame(notebook)

    notebook.add(add_entry_tab, text="Add Entry")
    notebook.add(database_tab, text="Food Database")
    notebook.add(recipes_tab, text="Recipes")
    notebook.add(log_tab, text="Daily Log")
    notebook.add(graphs_tab, text="Graphs")
    notebook.add(tracking_tab, text="Tracking")
    notebook.add(settings_tab, text="Settings")

    notebook.pack(fill="both", expand=True)

    build_add_entry_tab(add_entry_tab, conn)
    database_refresh = build_food_database_tab(database_tab, conn)
    recipes_refresh = build_recipes_tab(recipes_tab, conn)
    log_refresh = build_daily_log_tab(log_tab, conn)
    build_graphs_tab(graphs_tab, conn)
    tracking_refresh = build_tracking_tab(tracking_tab, conn)
    build_settings_tab(settings_tab, conn)

    # Refresh a tab's data whenever it's switched to, so changes made in other
    # tabs (e.g. logging a food) show up without needing a manual Load click.
    tab_refreshers = {
        str(database_tab): database_refresh,
        str(recipes_tab): recipes_refresh,
        str(log_tab): log_refresh,
        str(tracking_tab): tracking_refresh,
    }

    def on_tab_changed(_event):
        refresh_fn = tab_refreshers.get(notebook.select())
        if refresh_fn:
            refresh_fn()

    notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

    root.mainloop()


if __name__ == "__main__":
    import os

    from database import get_connection, initialize_database, seed_public_foods

    db_path = os.path.join(os.path.dirname(__file__), "macro_tracker.db")
    csv_path = os.path.join(os.path.dirname(__file__), "data", "common_foods.csv")

    _conn = get_connection(db_path)
    initialize_database(_conn)
    seed_public_foods(_conn, csv_path)
    main(_conn)
    _conn.close()
