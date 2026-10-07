"""Offline-first, black-and-white desktop school lunch planner.

Run with: python3 lunch_planner.py
Requires Python 3.10+ and Tkinter (included with most Python installations).
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from planner_core import (
    DAY_NAMES,
    MenuError,
    PlanDay,
    ScheduleError,
    generate_plan,
    load_menu,
    month_days,
    regenerate_day,
    remove_day,
)


BLACK = "#000000"
WHITE = "#ffffff"
FONT = ("Arial", 12)
SMALL_FONT = ("Arial", 10)
BOLD_FONT = ("Arial", 12, "bold")


def fetch_calendar_closures(year: int, month: int) -> set[date]:
    """Read all-day closure events from a configured Google Calendar.

    GOOGLE_CALENDAR_API_KEY and GOOGLE_SCHOOL_CALENDAR_ID are optional. The key
    stays on this computer and is used only for a read-only Google API call.
    """
    api_key = os.getenv("GOOGLE_CALENDAR_API_KEY")
    calendar_id = os.getenv("GOOGLE_SCHOOL_CALENDAR_ID")
    if not api_key or not calendar_id:
        return set()

    next_year = year + (month == 12)
    next_month = month % 12 + 1
    params = urlencode({
        "key": api_key,
        "timeMin": f"{year:04d}-{month:02d}-01T00:00:00Z",
        "timeMax": f"{next_year:04d}-{next_month:02d}-01T00:00:00Z",
        "singleEvents": "true",
        "maxResults": "2500",
    })
    url = (
        "https://www.googleapis.com/calendar/v3/calendars/"
        f"{quote(calendar_id, safe='')}/events?{params}"
    )
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=12) as response:
        payload = json.load(response)

    closures: set[date] = set()
    for event in payload.get("items", []):
        # Timed events are not assumed to mean the entire school day is closed.
        start_text = event.get("start", {}).get("date")
        if not start_text:
            continue
        start = date.fromisoformat(start_text)
        end_text = event.get("end", {}).get("date")
        end = date.fromisoformat(end_text) if end_text else start + timedelta(days=1)
        current = start
        while current < end:
            if current.year == year and current.month == month:
                closures.add(current)
            current += timedelta(days=1)
    return closures


class LunchPlanner(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("School lunch planner")
        self.geometry("1280x820")
        self.minsize(650, 500)
        self.configure(bg=WHITE)

        self.dishes = []
        self.plan: list[PlanDay] = []
        self.months = self._month_options()
        self.selected_month = tk.StringVar(value=self.months[0][1])
        self.status = tk.StringVar(value="Upload a CSV to begin.")
        self.file_label = tk.StringVar(value="No CSV selected")
        self.busy = False

        self._build_ui()
        self._render_calendar()

    @staticmethod
    def _month_options() -> list[tuple[str, str]]:
        today = date.today()
        first_year, first_month = today.year, today.month
        options = []
        for offset in range(12):
            total = first_year * 12 + first_month - 1 + offset
            year, zero_based_month = divmod(total, 12)
            month = zero_based_month + 1
            options.append((date(year, month, 1).strftime("%B %Y"), f"{year:04d}-{month:02d}"))
        return options

    def _button(self, parent: tk.Widget, text: str, command, *, filled: bool = False) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=SMALL_FONT,
            bg=BLACK if filled else WHITE,
            fg=WHITE if filled else BLACK,
            activebackground=WHITE if filled else BLACK,
            activeforeground=BLACK if filled else WHITE,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BLACK,
            padx=12,
            pady=8,
            cursor="hand2",
        )

    def _build_ui(self) -> None:
        heading = tk.Frame(self, bg=WHITE, highlightbackground=BLACK, highlightthickness=1)
        heading.pack(fill="x")
        tk.Label(heading, text="School lunch planner", bg=WHITE, fg=BLACK,
                 font=("Arial", 16, "bold"), padx=20, pady=17).pack(anchor="w")

        setup = tk.Frame(self, bg=WHITE, padx=20, pady=18,
                         highlightbackground=BLACK, highlightthickness=1)
        setup.pack(fill="x")
        controls = tk.Frame(setup, bg=WHITE)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)

        upload_frame = tk.Frame(controls, bg=WHITE)
        upload_frame.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        tk.Label(upload_frame, text="Menu CSV", bg=WHITE, fg=BLACK,
                 font=SMALL_FONT).pack(anchor="w", pady=(0, 8))
        upload_row = tk.Frame(upload_frame, bg=WHITE)
        upload_row.pack(fill="x")
        self.upload_button = self._button(upload_row, "Choose CSV", self._choose_csv)
        self.upload_button.pack(side="left")
        tk.Label(upload_row, textvariable=self.file_label, bg=WHITE, fg=BLACK,
                 font=SMALL_FONT, anchor="w").pack(side="left", padx=12)

        month_frame = tk.Frame(controls, bg=WHITE)
        month_frame.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        tk.Label(month_frame, text="Month", bg=WHITE, fg=BLACK,
                 font=SMALL_FONT).pack(anchor="w", pady=(0, 8))
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Plain.TCombobox", fieldbackground=WHITE, background=WHITE,
                        foreground=BLACK, bordercolor=BLACK, lightcolor=BLACK,
                        darkcolor=BLACK, arrowcolor=BLACK, padding=6)
        self.month_box = ttk.Combobox(
            month_frame,
            state="readonly",
            values=[label for label, _ in self.months],
            width=19,
            font=FONT,
            style="Plain.TCombobox",
        )
        self.month_box.current(0)
        self.month_box.pack()
        self.month_box.bind("<<ComboboxSelected>>", self._month_changed)

        self.generate_button = self._button(controls, "Generate menu", self._generate, filled=True)
        self.generate_button.grid(row=0, column=2, sticky="sew")
        self.generate_button.configure(state="disabled")

        tk.Label(setup, textvariable=self.status, bg=WHITE, fg=BLACK,
                 font=SMALL_FONT, anchor="w").pack(fill="x", pady=(15, 0))

        calendar_area = tk.Frame(self, bg=WHITE, padx=20, pady=18)
        calendar_area.pack(fill="both", expand=True)
        title_row = tk.Frame(calendar_area, bg=WHITE)
        title_row.pack(fill="x", pady=(0, 14))
        self.month_title = tk.Label(title_row, bg=WHITE, fg=BLACK,
                                     font=("Arial", 14, "bold"))
        self.month_title.pack(side="left")
        tk.Label(title_row, text="Monday–Friday", bg=WHITE, fg=BLACK,
                 font=SMALL_FONT).pack(side="right")

        outer = tk.Frame(calendar_area, bg=WHITE)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, bg=WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.calendar_frame = tk.Frame(self.canvas, bg=WHITE)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.calendar_frame, anchor="nw")
        self.calendar_frame.bind("<Configure>", self._update_scroll)
        self.canvas.bind("<Configure>", self._resize_calendar)
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)

    def _update_scroll(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_calendar(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _mousewheel(self, event) -> None:
        self.canvas.yview_scroll(-int(event.delta / 120), "units")

    def _chosen_year_month(self) -> tuple[int, int]:
        _, key = self.months[self.month_box.current()]
        year, month = key.split("-")
        return int(year), int(month)

    def _choose_csv(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose menu CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            dishes = load_menu(path)
        except (OSError, UnicodeError, MenuError) as exc:
            self.dishes = []
            self.plan = []
            self.generate_button.configure(state="disabled")
            self.file_label.set(Path(path).name)
            self.status.set(str(exc))
            self._render_calendar()
            return
        self.dishes = dishes
        self.plan = []
        self.file_label.set(Path(path).name)
        self.status.set(f"{len(dishes)} dishes loaded. Choose a month and generate the menu.")
        self.generate_button.configure(state="normal")
        self._render_calendar()

    def _month_changed(self, _event=None) -> None:
        self.plan = []
        self.status.set("Month changed. Generate a new menu." if self.dishes else "Upload a CSV to begin.")
        self._render_calendar()

    def _generate(self) -> None:
        if not self.dishes or self.busy:
            return
        year, month = self._chosen_year_month()
        self.busy = True
        self.generate_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.month_box.configure(state="disabled")
        self.status.set("Generating menu…")
        dishes = list(self.dishes)

        def work() -> None:
            warning = ""
            try:
                closures = fetch_calendar_closures(year, month)
            except Exception as exc:
                closures = set()
                warning = f" School calendar unavailable ({exc.__class__.__name__}); no dates imported."
            try:
                result = generate_plan(year, month, dishes, closures)
                self.after(0, lambda: self._generated(result, warning))
            except ScheduleError as exc:
                self.after(0, lambda error=str(exc): self._generation_failed(error + warning))

        threading.Thread(target=work, daemon=True).start()

    def _generated(self, result: list[PlanDay], warning: str) -> None:
        self.busy = False
        self.generate_button.configure(state="normal")
        self.upload_button.configure(state="normal")
        self.month_box.configure(state="readonly")
        self.plan = result
        count = sum(not item.closed for item in result)
        imported = sum(item.closed for item in result)
        suffix = f" {imported} no-school dates imported." if imported else ""
        self.status.set(f"{count} school lunches planned.{suffix}{warning}")
        self._render_calendar()

    def _generation_failed(self, error: str) -> None:
        self.busy = False
        self.generate_button.configure(state="normal")
        self.upload_button.configure(state="normal")
        self.month_box.configure(state="readonly")
        self.plan = []
        self.status.set(error)
        self._render_calendar()
        messagebox.showerror("No valid menu", error)

    def _regenerate(self, target_day: date) -> None:
        replacement = regenerate_day(self.plan, target_day, self.dishes)
        if replacement is None:
            self.status.set(f"No valid replacement for {target_day.strftime('%b %d')}.")
        else:
            self.plan = replacement
            self.status.set(f"{target_day.strftime('%b %d')} was regenerated.")
            self._render_calendar()

    def _remove(self, target_day: date) -> None:
        self.plan = remove_day(self.plan, target_day)
        self.status.set(f"{target_day.strftime('%b %d')} marked as no school.")
        self._render_calendar()

    def _render_calendar(self) -> None:
        for child in self.calendar_frame.winfo_children():
            child.destroy()
        self.month_title.configure(text=self.month_box.get())
        for column, name in enumerate(DAY_NAMES):
            self.calendar_frame.columnconfigure(column, weight=1, uniform="day")
            tk.Label(self.calendar_frame, text=name, bg=WHITE, fg=BLACK,
                     font=SMALL_FONT, anchor="w", padx=10, pady=8,
                     highlightbackground=BLACK, highlightthickness=1).grid(
                         row=0, column=column, sticky="nsew"
                     )

        year, month = self._chosen_year_month()
        days = self.plan if self.plan else month_days(year, month)
        by_day = {item.day: item for item in days}
        weeks = list(dict.fromkeys(item.week for item in days))
        for row, monday in enumerate(weeks, start=1):
            self.calendar_frame.rowconfigure(row, weight=1, minsize=190)
            for column in range(5):
                item = by_day.get(monday + timedelta(days=column))
                cell = tk.Frame(self.calendar_frame, bg=WHITE, padx=9, pady=9,
                                highlightbackground=BLACK, highlightthickness=1)
                cell.grid(row=row, column=column, sticky="nsew")
                if item is None:
                    continue
                tk.Label(cell, text=str(item.day.day), bg=WHITE, fg=BLACK,
                         font=BOLD_FONT, anchor="w").pack(fill="x", pady=(0, 12))
                tk.Frame(cell, bg=BLACK, height=1).pack(fill="x", pady=(0, 9))
                if item.closed:
                    tk.Label(cell, text="No school", bg=WHITE, fg=BLACK,
                             font=BOLD_FONT, anchor="w").pack(fill="x")
                    source = "School calendar" if item.closure_source == "calendar" else "Removed manually"
                    tk.Label(cell, text=source, bg=WHITE, fg=BLACK,
                             font=SMALL_FONT, anchor="w").pack(fill="x", pady=(4, 0))
                elif item.dish:
                    dish = item.dish
                    tk.Label(cell, text=dish.name, bg=WHITE, fg=BLACK,
                             font=BOLD_FONT, anchor="w", justify="left", wraplength=185).pack(fill="x")
                    tk.Label(cell, text=dish.restaurant, bg=WHITE, fg=BLACK,
                             font=SMALL_FONT, anchor="w").pack(fill="x", pady=(4, 0))
                    price = dish.regular_price
                    if dish.large_price:
                        price += f" · Large {dish.large_price}"
                    tk.Label(cell, text=price, bg=WHITE, fg=BLACK,
                             font=SMALL_FONT, anchor="w", wraplength=185).pack(fill="x", pady=(11, 0))
                    tk.Label(cell, text=f"{dish.protein_raw or 'Other'} · {dish.base_raw}",
                             bg=WHITE, fg=BLACK, font=SMALL_FONT,
                             anchor="w", wraplength=185).pack(fill="x", pady=(4, 0))
                    actions = tk.Frame(cell, bg=WHITE)
                    actions.pack(fill="x", side="bottom", pady=(12, 0))
                    self._button(actions, "Regenerate", lambda day=item.day: self._regenerate(day)).pack(
                        side="left", padx=(0, 7)
                    )
                    self._button(actions, "Remove", lambda day=item.day: self._remove(day)).pack(side="left")
                else:
                    tk.Label(cell, text="Waiting for menu", bg=WHITE, fg=BLACK,
                             font=SMALL_FONT, anchor="w").pack(fill="x")
        self._update_scroll()


if __name__ == "__main__":
    LunchPlanner().mainloop()
