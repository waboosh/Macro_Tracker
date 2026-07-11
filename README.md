# Macro Tracker

A desktop app for logging food and tracking daily macros. Log what you ate and how much,
and the app totals up your calories, protein, carbs, and fat for the day.

## How it works

- Look up a food (from a seeded public database or your own custom entries).
- Log how much of it you ate and when.
- Get a running summary of your daily calories, protein, carbs, and fat based on everything logged.

## Status

This project is under active development. Right now:

- The SQLite backend (`database.py`) supports adding/searching foods, logging entries, importing
  custom foods from CSV, and computing daily macro totals.
- `setup_db.py` initializes the database and seeds it with a starter set of common foods
  (`data/common_foods.csv`).
- The Tkinter GUI (`gui.py`) has a 4-tab shell (Add Entry, Food Database, Daily Log, Graphs) that
  isn't wired up to the backend yet.

More features, including the graphing view and full GUI wiring, are planned.

## Getting started

```bash
pip install -r requirements.txt
python setup_db.py   # creates and seeds macro_tracker.db
python gui.py         # launches the GUI shell
```
