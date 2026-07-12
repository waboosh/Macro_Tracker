# Macro Tracker

A desktop app for logging food and tracking daily macros. Log what you ate and how much,
and the app totals up your calories, protein, carbs, and fat for the day.

## Features

- **Add Entry** — search the food database (results filter live as you type), pick an item, and
  log it for a date/meal. Enter the amount in the food's native unit (grams, cups, pieces, etc.)
  and it converts to servings automatically.
- **Food Database** — browse and live-search ~90+ seeded public foods plus your own, add a
  custom food, or import a CSV of custom foods.
- **Recipes** — build a recipe (e.g. a daily protein shake) from multiple ingredients and
  amounts, and save it as a single loggable item — search for it in Add Entry just like any other
  food. Any ingredient not already in the food database gets added automatically. Recipes can be
  edited later; edits recompute the recipe's macros, including retroactively for past log entries.
- **Daily Log** — view logged entries for a date, delete one or more at once, see the day's macro
  totals, and export logged entries (with a daily-totals row per date) to CSV for a custom date
  range.
- **Graphs** — chart calories/protein/carbs/fat over a date range, one metric at a time or
  several together, with exact values labeled on each bar.
- **Tracking** — log your bodyweight (it carries forward day to day so you don't have to re-enter
  it) and a profile (gender, height, age); see your minimum daily protein target (0.7g per pound
  of bodyweight) and progress toward it; and estimate daily calorie targets to gain, maintain, or
  lose weight, based on the Mifflin-St Jeor BMR equation and an activity-level multiplier.

Today's date is preselected everywhere, and Food Database/Recipes/Daily Log/Tracking refresh
automatically when you switch to them, so changes made in one tab show up in another without a
manual reload.

## How it works

- Look up a food (from a seeded public database, your own custom entries, or a saved recipe).
- Log how much of it you ate and when.
- Get a running summary of your daily calories, protein, carbs, and fat based on everything logged,
  plus longer-range charts and progress toward your protein/calorie targets.

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py               # creates/seeds macro_tracker.db and launches the GUI
```

`requirements.txt` is pinned to versions resolved on the machine that generated it. If
`pip install -r requirements.txt` fails due to a Python version/platform mismatch, run
`pip install matplotlib` instead and let pip pick compatible versions.

## Building a standalone desktop app

A prebuilt, double-clickable `.exe` doesn't require Python or a terminal to launch — useful for
day-to-day personal use. Rebuild it after any code change:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "Macro Tracker" --icon "assets\icon.ico" --add-data "data;data" main.py
```

This produces `dist/Macro Tracker.exe`, a self-contained executable. The database
(`macro_tracker.db`) is created next to the `.exe` on first run and persists across runs/rebuilds,
so your logged data survives even after you rebuild the app. Pin `dist/Macro Tracker.exe` to the
Start menu/taskbar, or create a desktop shortcut to it, for one-click access.

## Project structure

- `database.py` — SQLite backend: schema, CRUD, CSV import/seed, macro totals, recipes,
  bodyweight/profile tracking.
- `gui.py` — Tkinter GUI (Add Entry, Food Database, Recipes, Daily Log, Graphs, Tracking tabs).
- `graphs.py` — matplotlib chart building for the Graphs tab.
- `main.py` — entry point: sets up the database, then launches the GUI.
- `setup_db.py` — standalone script to create/seed the database without launching the GUI.

## Status

Core functionality is in place and working end-to-end. Ideas for later: more chart types,
richer food/recipe editing and deletion from the UI, and unit conversions between more
serving formats.
