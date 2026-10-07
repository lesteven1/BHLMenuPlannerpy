"""CSV parsing and constraint-based scheduling for the school lunch planner."""

from __future__ import annotations

import csv
import io
import random
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable


HEADERS = (
    "dish name",
    "restaurant name",
    "day availability",
    "regular price",
    "large price (if applicable)",
    "protein type",
    "base type",
)

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
DAY_ALIASES = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "weds": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
}
PROTEINS = frozenset("CPBS")


class MenuError(ValueError):
    """Invalid uploaded menu."""


class ScheduleError(ValueError):
    """A complete schedule cannot be generated from the supplied menu."""


@dataclass(frozen=True)
class Dish:
    id: int
    name: str
    restaurant: str
    availability_raw: str
    weekdays: frozenset[int]
    regular_price: str
    large_price: str
    protein_raw: str
    proteins: frozenset[str]
    base_raw: str
    base: str


@dataclass(frozen=True)
class PlanDay:
    day: date
    dish: Dish | None = None
    closed: bool = False
    closure_source: str = ""

    @property
    def week(self) -> date:
        return self.day - timedelta(days=self.day.weekday())


def _availability(raw: str, row_number: int) -> frozenset[int]:
    if raw.casefold() == "all":
        return frozenset(range(5))
    parts = [part.strip().rstrip(".").casefold() for part in raw.split(",")]
    if not parts or any(part not in DAY_ALIASES for part in parts):
        raise MenuError(f"Row {row_number} has unsupported day availability: {raw!r}.")
    return frozenset(DAY_ALIASES[part] for part in parts)


def _proteins(raw: str) -> frozenset[str]:
    # Only valid combinations of the documented codes are recognized. Unknown
    # values such as "Fish" or "O" count as Other, not as shrimp or pork.
    compact = re.sub(r"[\s/,+&-]", "", raw.upper())
    if not compact or any(letter not in PROTEINS for letter in compact):
        return frozenset()
    return frozenset(compact)


def parse_menu(text: str) -> list[Dish]:
    try:
        rows = [row for row in csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
                if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise MenuError(f"Could not read the CSV: {exc}") from exc
    if not rows:
        raise MenuError("The CSV is empty.")
    if tuple(cell.strip().casefold() for cell in rows[0]) != HEADERS:
        raise MenuError("Expected these columns in order: " + ", ".join(HEADERS) + ".")

    dishes: list[Dish] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != 7:
            raise MenuError(f"Row {row_number} has {len(row)} columns; expected 7.")
        name, restaurant, availability, regular, large, protein, base = (
            cell.strip() for cell in row
        )
        if not all((name, restaurant, availability, regular, base)):
            raise MenuError(
                f"Row {row_number} needs a dish, restaurant, availability, "
                "regular price, and base type."
            )
        category = base.casefold() if base.casefold() in {"rice", "sushi"} else "other"
        dishes.append(Dish(
            id=row_number,
            name=name,
            restaurant=restaurant,
            availability_raw=availability,
            weekdays=_availability(availability, row_number),
            regular_price=regular,
            large_price=large,
            protein_raw=protein,
            proteins=_proteins(protein),
            base_raw=base,
            base=category,
        ))
    if not dishes:
        raise MenuError("The CSV contains no menu rows.")
    return dishes


def load_menu(path: str | Path) -> list[Dish]:
    return parse_menu(Path(path).read_text(encoding="utf-8-sig"))


def month_days(year: int, month: int, closures: Iterable[date] = ()) -> list[PlanDay]:
    if not 1 <= month <= 12:
        raise ValueError("Choose a valid month.")
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    closed = set(closures)
    days: list[PlanDay] = []
    current = start
    while current < end:
        if current.weekday() < 5:
            is_closed = current in closed
            days.append(PlanDay(
                day=current,
                closed=is_closed,
                closure_source="calendar" if is_closed else "",
            ))
        current += timedelta(days=1)
    return days


def _weekly_targets(days: list[PlanDay], phase: int) -> dict[date, tuple[int, int] | None]:
    weeks = list(dict.fromkeys(item.week for item in days))
    full_weeks = [
        week for week in weeks
        if len(group := [item for item in days if item.week == week]) == 5
        and not any(item.closed for item in group)
    ]
    targets: dict[date, tuple[int, int] | None] = {}
    for week in weeks:
        if week not in full_weeks:
            targets[week] = None
        else:
            sushi = int((full_weeks.index(week) + phase) % 2 == 0)
            targets[week] = (3 if sushi else 4, sushi)
    return targets


def validate_plan(days: list[PlanDay]) -> list[str]:
    errors: list[str] = []
    previous: PlanDay | None = None
    weeks = list(dict.fromkeys(item.week for item in days))
    sushi_counts: list[int] = []

    for item in days:
        if item.closed:
            if item.dish is not None:
                errors.append(f"{item.day}: closed day has a meal")
            previous = None
            continue
        if item.dish is None:
            errors.append(f"{item.day}: missing meal")
            previous = None
            continue
        if item.day.weekday() not in item.dish.weekdays:
            errors.append(f"{item.day}: dish is unavailable")
        if previous and previous.dish and previous.dish.proteins & item.dish.proteins:
            errors.append(f"{previous.day} and {item.day}: repeated protein")
        previous = item

    for week in weeks:
        group = [item for item in days if item.week == week]
        active = [item for item in group if not item.closed]
        counts = Counter(protein for item in active if item.dish for protein in item.dish.proteins)
        for protein, count in counts.items():
            if count > 2:
                errors.append(f"Week of {week}: {protein} appears {count} times")
        if len(group) == 5 and len(active) == 5 and all(item.dish for item in active):
            sushi = sum(item.dish.base == "sushi" for item in active if item.dish)
            rice = sum(item.dish.base == "rice" for item in active if item.dish)
            sushi_counts.append(sushi)
            if sushi not in (0, 1):
                errors.append(f"Week of {week}: {sushi} sushi meals")
            expected_rice = 3 if sushi == 1 else 4
            if rice != expected_rice:
                errors.append(f"Week of {week}: {rice} rice meals; expected {expected_rice}")

    if any(left + right != 1 for left, right in zip(sushi_counts, sushi_counts[1:])):
        errors.append("Consecutive full weeks must contain exactly one sushi meal")
    return errors


def generate_plan(
    year: int,
    month: int,
    dishes: list[Dish],
    closures: Iterable[date] = (),
    *,
    seed: int | None = None,
    max_nodes: int = 1_000_000,
) -> list[PlanDay]:
    if not dishes:
        raise ScheduleError("Upload a CSV with at least one dish.")
    template = month_days(year, month, closures)
    missing = next((weekday for weekday in range(5)
                    if any(day.day.weekday() == weekday and not day.closed for day in template)
                    and not any(weekday in dish.weekdays for dish in dishes)), None)
    if missing is not None:
        raise ScheduleError(f"No dishes are available on {DAY_NAMES[missing]}.")

    rng = random.Random(seed)
    phases = [0, 1]
    rng.shuffle(phases)
    total_nodes = 0

    for phase in phases:
        days = list(template)
        targets = _weekly_targets(days, phase)
        counts: dict[date, Counter[str]] = {}
        proteins: dict[date, Counter[str]] = {}
        uses: Counter[int] = Counter()

        def visit(index: int, previous_proteins: frozenset[str]) -> bool:
            nonlocal total_nodes
            total_nodes += 1
            if total_nodes > max_nodes:
                raise ScheduleError("The search took too long. Try a more varied CSV menu.")
            if index == len(days):
                return not validate_plan(days)

            item = days[index]
            if item.closed:
                return visit(index + 1, frozenset())
            week = item.week
            category_counts = counts.setdefault(week, Counter())
            protein_counts = proteins.setdefault(week, Counter())
            target = targets[week]
            remaining = sum(
                not later.closed and later.week == week for later in days[index + 1:]
            )

            candidates = list(dishes)
            rng.shuffle(candidates)
            candidates.sort(key=lambda dish: uses[dish.id])
            for dish in candidates:
                if item.day.weekday() not in dish.weekdays:
                    continue
                if previous_proteins & dish.proteins:
                    continue
                if any(protein_counts[protein] >= 2 for protein in dish.proteins):
                    continue
                if target is not None:
                    rice_target, sushi_target = target
                    category_target = {
                        "rice": rice_target,
                        "sushi": sushi_target,
                        "other": 5 - rice_target - sushi_target,
                    }
                    if category_counts[dish.base] >= category_target[dish.base]:
                        continue

                days[index] = replace(item, dish=dish)
                category_counts[dish.base] += 1
                protein_counts.update(dish.proteins)
                uses[dish.id] += 1

                possible = True
                if target is not None:
                    needs = sum(
                        category_target[category] - category_counts[category]
                        for category in ("rice", "sushi", "other")
                    )
                    possible = needs <= remaining
                if possible and visit(index + 1, dish.proteins):
                    return True

                uses[dish.id] -= 1
                protein_counts.subtract(dish.proteins)
                category_counts[dish.base] -= 1
                days[index] = item
            return False

        if visit(0, frozenset()):
            return days

    raise ScheduleError(
        "No complete schedule satisfies every rule. Check weekday availability "
        "and the protein, rice, sushi, and other-base balance in the CSV."
    )


def regenerate_day(days: list[PlanDay], target_day: date, dishes: list[Dish],
                   *, seed: int | None = None) -> list[PlanDay] | None:
    index = next((i for i, item in enumerate(days) if item.day == target_day), None)
    if index is None or days[index].closed or days[index].dish is None:
        return None
    uses = Counter(item.dish.id for item in days if item.dish)
    rng = random.Random(seed)
    candidates = [dish for dish in dishes
                  if dish.id != days[index].dish.id and target_day.weekday() in dish.weekdays]
    rng.shuffle(candidates)
    candidates.sort(key=lambda dish: uses[dish.id])
    for dish in candidates:
        candidate = list(days)
        candidate[index] = replace(candidate[index], dish=dish)
        if not validate_plan(candidate):
            return candidate
    return None


def remove_day(days: list[PlanDay], target_day: date) -> list[PlanDay]:
    if not any(item.day == target_day and not item.closed for item in days):
        return list(days)
    return [replace(item, dish=None, closed=True, closure_source="manual")
            if item.day == target_day else item for item in days]
