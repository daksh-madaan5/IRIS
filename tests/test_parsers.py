import unittest

from src.cleaning.parsers import (
    parse_legacy_month,
    parse_month,
    parse_number,
    parse_project_identity,
    split_parenthesized_pair,
    split_legacy_triplet,
)


class ParserTests(unittest.TestCase):
    def test_numeric_parser(self):
        self.assertEqual(parse_number("12,816.45"), 12816.45)
        self.assertEqual(parse_number("89.7%"), 89.7)
        self.assertIsNone(parse_number("-"))
        self.assertIsNone(parse_number("NA"))

    def test_date_parser(self):
        self.assertEqual(parse_month("03/2027"), "2027-03")
        self.assertIsNone(parse_month("NA"))
        self.assertIsNone(parse_month("13/2027"))

    def test_legacy_date_parser_preserves_missing_and_accepts_reported_formats(self):
        self.assertEqual(parse_legacy_month("10-2013"), "2013-10")
        self.assertEqual(parse_legacy_month("Jun-2023"), "2023-06")
        self.assertEqual(parse_legacy_month("9/2018"), "2018-09")
        self.assertIsNone(parse_legacy_month("N.A."))

    def test_legacy_date_parser_accepts_character_spaced_2025_source_forms(self):
        self.assertEqual(parse_legacy_month("2 - 2 0 1 8"), "2018-02")
        self.assertEqual(parse_legacy_month("7 / 2 019"), "2019-07")
        self.assertEqual(parse_legacy_month("May-23"), "2023-05")
        self.assertEqual(parse_legacy_month("J u n -24"), "2024-06")
        self.assertIsNone(parse_legacy_month("N . A ."))
        self.assertIsNone(parse_legacy_month("N .A."))

    def test_legacy_triplet_does_not_promote_anticipated_value(self):
        self.assertEqual(
            split_legacy_triplet("235.72\n(N.A.)\n{235.72}"),
            ("235.72", None, "235.72"),
        )
        self.assertEqual(
            split_legacy_triplet("3/2024\n(-)\n[6/2024]"),
            ("3/2024", None, "6/2024"),
        )
        self.assertEqual(split_legacy_triplet("/\n(-)\n[3/2024]"), (None, None, "3/2024"))

    def test_parenthesized_values(self):
        self.assertEqual(split_parenthesized_pair("265.91\n(265.91)"), ("265.91", "265.91"))
        self.assertEqual(split_parenthesized_pair("03/2027\n(11/2026)"), ("03/2027", "11/2026"))
        self.assertEqual(split_parenthesized_pair("03/2027\n(-)"), ("03/2027", None))

    def test_multiline_project_name_and_identifiers(self):
        cell = "Very long project name\ncontinued on another line\n(Long Agency Name)\n(612786)\n(-) (PMG-9)"
        parsed = parse_project_identity(cell)
        self.assertEqual(parsed.project_name, "Very long project name continued on another line")
        self.assertEqual(parsed.agency, "Long Agency Name")
        self.assertEqual(parsed.project_code, "612786")
        self.assertIsNone(parsed.legacy_ocms_code)
        self.assertEqual(parsed.pmgid, "PMG-9")

    def test_separate_legacy_identifier_layout(self):
        parsed = parse_project_identity("Project Name\n(Agency Name)\n(612786)\n(N04000106)")
        self.assertEqual(parsed.project_name, "Project Name")
        self.assertEqual(parsed.agency, "Agency Name")
        self.assertEqual(parsed.project_code, "612786")
        self.assertEqual(parsed.legacy_ocms_code, "N04000106")
        self.assertIsNone(parsed.pmgid)

    def test_separate_missing_legacy_identifier_layout(self):
        parsed = parse_project_identity("Project Name\n(Agency Name)\n(612183)\n(-)")
        self.assertEqual(parsed.project_code, "612183")
        self.assertIsNone(parsed.legacy_ocms_code)

    def test_detail_milestones_row_cleaning(self):
        from src.extraction.pipeline import _clean_detail_milestones_row
        pending = {
            "serial": 1,
            "source_page": 96,
            "source_pages": "96",
            "source_row_number": 2,
            "sector": "ATOMIC ENERGY",
            "cells": [
                "1",
                "PROTOTYPE FAST BREEDER REACTOR (BHAVINI, 500 MWE) - [020100044],BHAVNI,TAMIL NADU",
                "10/2003",
                "9/2007\n(-)\n[12/2024]",
                "3492\n(5677)\n{6840}",
                "6209.77\n2185\n207",
                "33 / 37",
            ],
        }
        cleaned = _clean_detail_milestones_row(pending, "2024-01", "FR_jan_2024.pdf")
        self.assertEqual(cleaned["project_code"], "020100044")
        self.assertEqual(cleaned["project_name"], "PROTOTYPE FAST BREEDER REACTOR (BHAVINI, 500 MWE)")
        self.assertEqual(cleaned["agency"], "BHAVNI")
        self.assertEqual(cleaned["state"], "TAMIL NADU")
        self.assertEqual(cleaned["sector"], "ATOMIC ENERGY")
        self.assertIsNone(cleaned["ministry"])
        self.assertIsNone(cleaned["start_date"])
        self.assertIsNone(cleaned["physical_progress"])
        self.assertEqual(cleaned["approval_date"], "2003-10")
        self.assertEqual(cleaned["original_completion_date"], "2007-09")
        self.assertIsNone(cleaned["revised_completion_date"])
        self.assertEqual(cleaned["original_cost"], 3492.0)
        self.assertEqual(cleaned["revised_cost"], 5677.0)
        self.assertEqual(cleaned["cumulative_expenditure"], 6209.77)


if __name__ == "__main__":
    unittest.main()
