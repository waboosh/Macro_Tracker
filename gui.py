import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from database import (
    add_food,
    add_log_entry,
    delete_log_entry,
    get_all_foods,
    get_daily_macro_totals,
    get_log_entries_by_date,
    get_macro_totals_by_date_range,
    import_custom_foods,
    search_foods_by_name,
)
from graphs import METRICS, build_metric_figure

MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack"]


UNIT_LABELS = {"g": "Grams", "piece": "Pieces", "cup": "Cups", "slice": "Slices", "tbsp": "Tbsp"}


def label_for_unit(unit):
    """Human-friendly label for a food's native serving unit, e.g. 'cup' -> 'Cups'."""
    return UNIT_LABELS.get(unit.strip().lower(), unit.strip().capitalize())


def build_add_entry_tab(parent, conn):
    """Search foods, pick one, and log it against a date/meal/servings."""
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

    def run_search(*_):
        results_tree.delete(*results_tree.get_children())
        results_by_id.clear()
        name = search_var.get().strip()
        if not name:
            return
        for row in search_foods_by_name(conn, name):
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

    search_entry.bind("<Return>", run_search)
    ttk.Button(search_frame, text="Search", command=run_search).pack(side="left")

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
    ttk.Entry(entry_frame, textvariable=date_var).grid(row=1, column=1, sticky="ew", pady=2)

    ttk.Label(entry_frame, text="Meal:").grid(row=2, column=0, sticky="w")
    meal_var = tk.StringVar(value=MEAL_TYPES[0])
    ttk.Combobox(entry_frame, textvariable=meal_var, values=MEAL_TYPES, state="readonly").grid(
        row=2, column=1, sticky="ew", pady=2
    )

    amount_label = ttk.Label(entry_frame, text="Amount eaten:")
    amount_label.grid(row=3, column=0, sticky="w")
    amount_var = tk.StringVar()
    amount_entry = ttk.Entry(entry_frame, textvariable=amount_var, state="disabled")
    amount_entry.grid(row=3, column=1, sticky="ew", pady=2)

    ttk.Label(entry_frame, text="Servings:").grid(row=4, column=0, sticky="w")
    servings_var = tk.StringVar()
    ttk.Entry(entry_frame, textvariable=servings_var).grid(row=4, column=1, sticky="ew", pady=2)

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


def build_daily_log_tab(parent, conn):
    """View logged entries for a date, delete them, and see the day's totals."""
    controls_frame = ttk.Frame(parent, padding=10)
    controls_frame.pack(fill="x")

    ttk.Label(controls_frame, text="Date (YYYY-MM-DD):").pack(side="left")
    date_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(controls_frame, textvariable=date_var).pack(side="left", fill="x", expand=True, padx=5)

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

    refresh()


def build_graphs_tab(parent, conn):
    """Chart daily calories and/or macros over a date range, one metric at a time or combined."""
    controls_frame = ttk.Frame(parent, padding=10)
    controls_frame.pack(fill="x")

    ttk.Label(controls_frame, text="Start date:").pack(side="left")
    start_var = tk.StringVar(value=(date.today() - timedelta(days=6)).isoformat())
    ttk.Entry(controls_frame, textvariable=start_var, width=12).pack(side="left", padx=5)

    ttk.Label(controls_frame, text="End date:").pack(side="left")
    end_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(controls_frame, textvariable=end_var, width=12).pack(side="left", padx=5)

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
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
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
        tree.column(col, width=85, anchor="e" if col != "source" else "center")
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
    ttk.Button(search_frame, text="Search", command=refresh).pack(side="left")

    def show_all():
        search_var.set("")
        refresh()

    ttk.Button(search_frame, text="Show All", command=show_all).pack(side="left", padx=(5, 0))

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
    for i, (label, key) in enumerate(field_specs):
        row, col = divmod(i, 4)
        ttk.Label(add_frame, text=f"{label}:").grid(row=row * 2, column=col, sticky="w", padx=2)
        var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=var, width=14).grid(
            row=row * 2 + 1, column=col, sticky="ew", padx=2, pady=(0, 5)
        )
        fields[key] = var
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


def main(conn):
    root = tk.Tk()
    root.title("Macro Tracker")
    root.geometry("800x600")

    notebook = ttk.Notebook(root)

    add_entry_tab = ttk.Frame(notebook)
    database_tab = ttk.Frame(notebook)
    log_tab = ttk.Frame(notebook)
    graphs_tab = ttk.Frame(notebook)

    notebook.add(add_entry_tab, text="Add Entry")
    notebook.add(database_tab, text="Food Database")
    notebook.add(log_tab, text="Daily Log")
    notebook.add(graphs_tab, text="Graphs")

    notebook.pack(fill="both", expand=True)

    build_add_entry_tab(add_entry_tab, conn)
    build_food_database_tab(database_tab, conn)
    build_daily_log_tab(log_tab, conn)
    build_graphs_tab(graphs_tab, conn)

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
