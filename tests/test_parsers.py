import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ics import Calendar

from myfap.parsers import convert_schedule_to_ics, parse_marks_html


FIXTURES = Path(__file__).parent / "fixtures"


class MarksParserTests(unittest.TestCase):
    def test_category_stops_at_the_end_of_rowspan(self):
        html = (FIXTURES / "marks_rowspan.html").read_text(encoding="utf-8")

        self.assertEqual(parse_marks_html(html), [
            {"category": "Quiz", "item": "Q1", "weight": "10%", "value": "8", "comment": ""},
            {"category": "Quiz", "item": "Q2", "weight": "10%", "value": "7", "comment": "Completed"},
            {"category": "Final", "item": "FE", "weight": "80%", "value": "6", "comment": "Passed"},
        ])

    def test_colspan_summary_preserves_compatibility_snapshot(self):
        html = (FIXTURES / "marks_colspan.html").read_text(encoding="utf-8")

        self.assertEqual(parse_marks_html(html), [
            {"category": "Final", "item": "FE", "weight": "100%", "value": "7.3", "comment": "Passed"},
            {"category": "Final", "item": "Average", "value": "7.3"},
            {"category": "Final", "item": "Status", "value": "Passed"},
        ])

    def test_missing_table_returns_empty_list(self):
        self.assertEqual(parse_marks_html("<p>No marks</p>"), [])


class ScheduleParserTests(unittest.TestCase):
    def test_ics_preserves_vietnam_time_and_session_details(self):
        data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))

        calendar = Calendar(convert_schedule_to_ics(data))

        self.assertEqual(len(calendar.events), 1)
        event = next(iter(calendar.events))
        self.assertEqual(event.name, "TEST101 (Online)")
        self.assertEqual(event.begin.datetime, datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc))
        self.assertEqual(event.end.datetime, datetime(2026, 10, 15, 2, 50, tzinfo=timezone.utc))
        self.assertEqual(event.location, "Demo room")
        self.assertEqual(event.description, "\n".join([
            "Group: Demo group", "Session: 1", "Lecturer: Demo lecturer",
            "Room: Demo room", "Meet URL: https://example.invalid/meet",
        ]))

    def test_empty_schedule_returns_valid_empty_calendar(self):
        data = json.loads((FIXTURES / "schedule_empty.json").read_text(encoding="utf-8"))

        self.assertEqual(len(Calendar(convert_schedule_to_ics(data)).events), 0)

    def test_non_list_schedule_is_rejected(self):
        data = json.loads((FIXTURES / "schedule_malformed.json").read_text(encoding="utf-8"))

        with self.assertRaises(ValueError):
            convert_schedule_to_ics(data)

    def test_invalid_root_or_missing_session_fields_are_rejected(self):
        for data in [None, [], {}, {"data": None}, {"data": [None]}, {"data": [{}]}]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    convert_schedule_to_ics(data)

    def test_required_session_fields_reject_non_string_and_blank_values(self):
        for field in ("date", "slotTime", "subjectCode"):
            for value in (None, 123, " "):
                with self.subTest(field=field, value=value):
                    data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
                    data["data"][0][field] = value

                    with self.assertRaises(ValueError):
                        convert_schedule_to_ics(data)

    def test_invalid_session_date_or_slot_is_rejected(self):
        for field, value in [("date", "02/30/2026"), ("slotTime", "invalid")]:
            with self.subTest(field=field):
                data = json.loads((FIXTURES / "schedule_valid.json").read_text(encoding="utf-8"))
                data["data"][0][field] = value

                with self.assertRaises(ValueError):
                    convert_schedule_to_ics(data)


if __name__ == "__main__":
    unittest.main()
