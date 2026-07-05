import tkinter as tk
from tkinter import ttk

def main():
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

    root.mainloop()

if __name__ == "__main__":
    main()