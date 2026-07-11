# Macro Tracker

A desktop app for logging food and tracking daily macros. Log what you ate and how much,
and the app totals up your calories, protein, carbs, and fat for the day.

## Features

- **Add Entry** — search the food database, pick an item, and log it for a date/meal. Enter
  the amount in the food's native unit (grams, cups, pieces, etc.) and it converts to servings
  automatically.
- **Food Database** — browse and search all foods, add your own custom foods, or import a CSV
  of custom foods.
- **Daily Log** — view logged entries for a given date, delete one or more at once, and see the
  day's macro totals.
- **Graphs** — chart calories/protein/carbs/fat over a date range, one metric at a time or
  several together, with exact values labeled on each bar.

## How it works

- Look up a food (from a seeded public database or your own custom entries).
- Log how much of it you ate and when.
- Get a running summary of your daily calories, protein, carbs, and fat based on everything logged.

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

## Project structure

- `database.py` — SQLite backend: schema, CRUD, CSV import/seed, macro totals.
- `gui.py` — Tkinter GUI (all four tabs).
- `graphs.py` — matplotlib chart building for the Graphs tab.
- `main.py` — entry point: sets up the database, then launches the GUI.
- `setup_db.py` — standalone script to create/seed the database without launching the GUI.

## Status

Core functionality is in place and working end-to-end. Ideas for later: more chart types,
richer food editing/deletion in the Food Database tab, and unit conversions between more
serving formats.
