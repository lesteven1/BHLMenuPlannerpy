import unittest
from datetime import date

from planner_core import (
    Dish,
    MenuError,
    ScheduleError,
    generate_plan,
    month_days,
    parse_menu,
    regenerate_day,
    remove_day,
    validate_plan,
)


HEADER = (
    "dish name,restaurant name,day availability,regular price,"
    "large price (if applicable),protein type,base type"
)


def dish(identifier, *, weekdays=range(5), protein="", base="rice"):
    return Dish(
        id=identifier,
        name=f"Dish {identifier}",
        restaurant="Test restaurant",
        availability_raw="All",
        weekdays=frozenset(weekdays),
        regular_price="$10",
        large_price="",
        protein_raw=protein,
        proteins=frozenset(protein),
        base_raw=base,
        base=base,
    )


class CsvTests(unittest.TestCase):
    def test_headers_mixed_proteins_and_other_values(self):
        text = (
            HEADER.upper() + "\n"
            '"Chicken, pork bowl",Cafe,"Thurs, Fri",$12,,C/P,Rice\n'
            'Fish bowl,Cafe,All,$11,,Fish,M\n'
        )
        parsed = parse_menu(text)
        self.assertEqual(parsed[0].weekdays, frozenset({3, 4}))
        self.assertEqual(parsed[0].proteins, frozenset({"C", "P"}))
        self.assertEqual(parsed[1].proteins, frozenset())
        self.assertEqual(parsed[1].base, "other")

    def test_invalid_headers_and_rows(self):
        with self.assertRaises(MenuError):
            parse_menu("wrong,headers\n1,2")
        with self.assertRaises(MenuError):
            parse_menu(HEADER + "\nOnly one cell")


class SolverTests(unittest.TestCase):
    def setUp(self):
        # Sushi may occur any weekday; Tuesday-only dish tests availability.
        self.dishes = [
            dish(1, protein="C", base="rice"),
            dish(2, protein="P", base="rice"),
            dish(3, protein="B", base="rice"),
            dish(4, protein="S", base="rice"),
            dish(5, protein="", base="rice"),
            dish(6, protein="", base="sushi"),
            dish(7, protein="", base="other"),
            dish(8, weekdays={1}, protein="C", base="rice"),
            dish(9, protein="CP", base="rice"),
        ]

    def test_full_plan_and_availability(self):
        plan = generate_plan(2026, 9, self.dishes, seed=7)
        self.assertEqual(validate_plan(plan), [])
        self.assertEqual(len(plan), 22)
        self.assertTrue(all(item.day.weekday() == 1 for item in plan if item.dish.id == 8))

    def test_regenerate_changes_only_one_day(self):
        plan = generate_plan(2026, 9, self.dishes, seed=8)
        target = plan[1].day
        next_plan = regenerate_day(plan, target, self.dishes, seed=9)
        self.assertIsNotNone(next_plan)
        self.assertEqual(validate_plan(next_plan), [])
        self.assertEqual(
            [a.day for a, b in zip(plan, next_plan) if a.dish != b.dish],
            [target],
        )

    def test_remove_changes_only_one_day(self):
        plan = generate_plan(2026, 9, self.dishes, seed=10)
        target = plan[1].day
        next_plan = remove_day(plan, target)
        self.assertEqual([a.day for a, b in zip(plan, next_plan) if a != b], [target])
        self.assertTrue(next_plan[1].closed)
        self.assertIsNone(next_plan[1].dish)
        self.assertEqual(validate_plan(next_plan), [])

    def test_impossible_plan_is_reported(self):
        with self.assertRaises(ScheduleError):
            generate_plan(2026, 9, [dish(1, protein="C")], seed=1)

    def test_mixed_protein_conflict(self):
        days = month_days(2026, 9)
        days[0] = type(days[0])(days[0].day, self.dishes[0])
        days[1] = type(days[1])(days[1].day, self.dishes[-1])
        self.assertTrue(any("repeated protein" in error for error in validate_plan(days)))


if __name__ == "__main__":
    unittest.main()
