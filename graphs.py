"""Build matplotlib figures from macro-tracking data."""

from matplotlib.figure import Figure

METRICS = {
    "calories": {"label": "Calories (kcal)", "color": "#4C72B0", "index": 1, "fmt": "%.0f"},
    "protein": {"label": "Protein (g)", "color": "tab:red", "index": 2, "fmt": "%.1f"},
    "carbs": {"label": "Carbs (g)", "color": "tab:green", "index": 3, "fmt": "%.1f"},
    "fat": {"label": "Fat (g)", "color": "tab:orange", "index": 4, "fmt": "%.1f"},
}


def build_metric_figure(rows, metric_keys):
    """Bar chart of the selected metric(s) per day, with exact values labeled on each bar.

    rows: [(date, calories, protein, carbs, fat), ...] as returned by
    database.get_macro_totals_by_date_range. metric_keys: subset of METRICS keys.
    """
    dates = [row[0] for row in rows]
    fig = Figure(figsize=(7, 5), dpi=100)
    ax = fig.add_subplot(111)

    all_values = []
    if len(metric_keys) == 1:
        info = METRICS[metric_keys[0]]
        values = [row[info["index"]] or 0 for row in rows]
        all_values.extend(values)
        bars = ax.bar(dates, values, color=info["color"])
        ax.bar_label(bars, fmt=info["fmt"], padding=3)
        ax.set_ylabel(info["label"])
        ax.set_title(info["label"])
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45)
    else:
        slot_count = len(metric_keys)
        slot_width = 0.8 / slot_count
        positions = range(len(dates))
        for i, key in enumerate(metric_keys):
            info = METRICS[key]
            values = [row[info["index"]] or 0 for row in rows]
            all_values.extend(values)
            offset = (i - (slot_count - 1) / 2) * slot_width
            bars = ax.bar(
                [p + offset for p in positions], values, width=slot_width, color=info["color"], label=info["label"]
            )
            ax.bar_label(bars, fmt=info["fmt"], padding=2, fontsize=7, rotation=90)
        ax.set_xticks(list(positions))
        ax.set_xticklabels(dates, rotation=45)
        ax.set_ylabel("Value")
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)

    ax.set_xlabel("Date")
    if all_values:
        ax.set_ylim(0, max(all_values) * 1.2 or 1)

    fig.tight_layout()
    if len(metric_keys) > 1:
        fig.subplots_adjust(right=0.78)
    return fig
