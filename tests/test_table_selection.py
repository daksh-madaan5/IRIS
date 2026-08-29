import unittest
from pathlib import Path

import pdfplumber

from src.extraction.pipeline import (
    ANNEXURE_XVIII_LAYOUT,
    LEGACY_DETAIL_MILESTONES_LAYOUT,
    TableCandidateSelectionError,
    _detect_report_month,
    _locate_table6_candidate,
    _repair_legacy_project_code_bleed,
    _select_table6_candidate,
)


class FakeTable:
    def __init__(self, rows, bbox=(10, 10, 500, 700)):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows


CANONICAL_HEADER = [
    "Sl.No",
    "Project Name (Agency) (Project Code)",
    "State",
    "Date of Approval (Start Date) MM/YYYY",
    "Original/Target DoC (Revised DoC) MM/YYYY",
    "Original Cost Revised Cost in Rs. Crore",
    "Cumulative Expenditure in Rs. Crore",
    "Physical Progress (%)",
]
CANONICAL_ROW = ["1", "Example (Agency) (612786)", "State", "01/2020", "01/2025", "1", "1", "1"]


class TableSelectionRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def _assert_pdf_page_selects_one(self, relative_path: str, page_number: int, expected_detected: int):
        with pdfplumber.open(self.root / relative_path) as pdf:
            page = pdf.pages[page_number - 1]
            selected, _, _, audits, _ = _locate_table6_candidate(page, page_number)
        self.assertEqual(sum(audit["detection_pass"] == "full_page" for audit in audits), expected_detected)
        self.assertEqual(sum(audit["matches_table6_signature"] for audit in audits), 1)
        self.assertEqual(len(selected[0]), 8)
        self.assertIn("Project Name", selected[0][1])
        self.assertTrue(any(row[0] and row[0].isdigit() for row in selected[1:]))
        return audits

    def test_january_first_table6_page_ignores_enclosing_table(self):
        audits = self._assert_pdf_page_selects_one("data/raw/FlashReport_January_2026.pdf", 62, 2)
        ignored = [audit for audit in audits if not audit["matches_table6_signature"]]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]["column_count"], 2)
        self.assertFalse(ignored[0]["bbox_within_page"])
        self.assertIn("expected 8 columns", ignored[0]["reason"])

    def test_february_first_table6_page_ignores_enclosing_table(self):
        self._assert_pdf_page_selects_one("data/raw/FlashReport_February_2026.pdf", 65, 2)

    def test_march_first_table6_page_ignores_enclosing_table(self):
        self._assert_pdf_page_selects_one("data/raw/FlashReport_March_2026.pdf", 55, 2)

    def test_april_normal_table6_page_selects_canonical_table(self):
        audits = self._assert_pdf_page_selects_one("data/raw/FlashReport_April2026.pdf", 55, 1)
        self.assertTrue(audits[0]["bbox_within_page"])

    def test_july_2025_approval_only_layout_selects_semantically(self):
        audits = self._assert_pdf_page_selects_one("data/raw/2025/FlashReport_July_2025.pdf", 37, 2)
        matching = [audit for audit in audits if audit["matches_table6_signature"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["layout_version"], "table6-eight-column-approval-only-v1")

    def test_legacy_april_to_june_pages_select_nine_column_layout(self):
        cases = (
            ("data/raw/2025/FR_April_2025.pdf", 43),
            ("data/raw/2025/FR_May2025.pdf", 43),
            ("data/raw/2025/FR_JUNE_2025.pdf", 41),
        )
        for path, page_number in cases:
            with self.subTest(path=path):
                with pdfplumber.open(self.root / path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(pdf.pages[page_number - 1], page_number)
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], "legacy-all-ongoing-nine-column-v1")
                self.assertEqual(len(selected[0]), 9)
                self.assertTrue(any(row[2] and row[2].isdigit() for row in selected[1:]))

    def test_november_2024_progress_only_legacy_layout_selects_semantically(self):
        path = self.root / "data/raw/2024/November.pdf"
        with pdfplumber.open(path) as pdf:
            selected, _, _, audits, _ = _locate_table6_candidate(pdf.pages[45], 46)
        matching = [audit for audit in audits if audit["matches_table6_signature"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(
            matching[0]["layout_version"],
            "legacy-all-ongoing-nine-column-progress-only-v1",
        )
        self.assertEqual(len(selected[0]), 9)
        self.assertNotIn("Physical", selected[0][8])
        self.assertTrue(any(row[2] and row[2].isdigit() for row in selected[1:]))

    def test_april_and_may_2024_annexure_xviii_select_by_own_signature(self):
        cases = (
            ("data/raw/2024/April_Part-II_List_of_tables.pdf", 462),
            ("data/raw/2024/May_Part-2.pdf", 462),
        )
        for relative_path, page_number in cases:
            with self.subTest(relative_path=relative_path):
                with pdfplumber.open(self.root / relative_path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(pdf.pages[page_number - 1], page_number)
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], ANNEXURE_XVIII_LAYOUT)
                header_index = 1 if "Details of Ongoing Projects" in (selected[0][0] or "") else 0
                self.assertEqual(len(selected[header_index]), 6)
                self.assertIn("SI.No", selected[header_index][0])

    def test_annexure_continuation_requires_annexure_header_context(self):
        with pdfplumber.open(self.root / "data/raw/2024/May_Part-2.pdf") as pdf:
            page = pdf.pages[471]
            with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
                _locate_table6_candidate(page, 472)
            selected, _, _, audits, _ = _locate_table6_candidate(page, 472, ANNEXURE_XVIII_LAYOUT)
        matching = [audit for audit in audits if audit["matches_table6_signature"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["layout_version"], ANNEXURE_XVIII_LAYOUT)
        self.assertEqual(len(selected[0]), 6)

    def test_month_fallback_uses_scoped_parent_year_for_part_file(self):
        path = self.root / "data/raw/2024/May_Part-2.pdf"
        self.assertEqual(_detect_report_month("Annexure XVIII", path.name, path), "2024-05")

    def test_legacy_code_bleed_repair_requires_independent_shift_evidence(self):
        unsafe = [
            ["", "", "1", "PROJECT ONE\n(AAI)", "", "", "", "", ""],
            ["", "", "2", "(N04000073)\nPROJECT TWO\n(AAI)", "", "", "", "", ""],
        ]
        self.assertEqual(_repair_legacy_project_code_bleed(unsafe, "(N04000073)"), [])
        self.assertNotIn("N04000073", unsafe[0][3])

        shifted = [
            ["", "", "1", "PROJECT ONE\n(AAI)", "", "", "", "", ""],
            ["", "", "2", "(N04000073)\nPROJECT TWO\n(AAI)\n(N04000074)", "", "", "", "", ""],
        ]
        repairs = _repair_legacy_project_code_bleed(shifted, "(N04000073) (N04000074)")
        self.assertEqual(len(repairs), 1)
        self.assertIn("(N04000073)", shifted[0][3])
        self.assertNotIn("(N04000073)", shifted[1][3])
        self.assertIn("(N04000074)", shifted[1][3])

    def test_unique_unassigned_final_code_is_required_for_last_row_repair(self):
        table = [["", "", "1", "PROJECT ONE\n(AAI)", "", "", "", "", ""]]
        repairs = _repair_legacy_project_code_bleed(table, "PROJECT ONE (N04000073)")
        self.assertEqual(repairs[0]["method"], "unique_unassigned_final_page_code")
        self.assertIn("(N04000073)", table[0][3])

        ambiguous = [["", "", "1", "PROJECT ONE\n(AAI)", "", "", "", "", ""]]
        self.assertEqual(
            _repair_legacy_project_code_bleed(ambiguous, "(N04000073) (N04000074)"),
            [],
        )

    def test_page_frame_exclusion_recovers_merged_grid_pages(self):
        cases = (
            ("data/raw/FlashReport_January_2026.pdf", 76),
            ("data/raw/FlashReport_February_2026.pdf", 79),
            ("data/raw/FlashReport_March_2026.pdf", 70),
        )
        for path, page_number in cases:
            with self.subTest(path=path, page_number=page_number):
                audits = self._assert_pdf_page_selects_one(path, page_number, 1)
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(matching[0]["detection_pass"], "page_frame_excluded")
                self.assertTrue(any(audit["column_count"] == 10 for audit in audits if not audit["matches_table6_signature"]))

    def test_zero_matching_candidates_fails_closed(self):
        table = FakeTable([["not", "a project table"], ["", ""]])
        with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
            _select_table6_candidate([table], 1, 600, 800)

    def test_multiple_matching_candidates_fails_closed(self):
        left = FakeTable([CANONICAL_HEADER, CANONICAL_ROW])
        right = FakeTable([CANONICAL_HEADER, CANONICAL_ROW], bbox=(20, 20, 510, 710))
        with self.assertRaisesRegex(TableCandidateSelectionError, "found 2"):
            _select_table6_candidate([left, right], 1, 600, 800)

    def test_eight_columns_without_semantic_signature_is_rejected(self):
        wrong = FakeTable([["x"] * 8, ["1"] + ["value"] * 7])
        with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
            _select_table6_candidate([wrong], 1, 600, 800)

    def test_legacy_continuation_accepts_7_column_without_header(self):
        # 7 columns
        table = FakeTable([["1"] + ["value"] * 6])
        data, index, audits = _select_table6_candidate([table], 1, 600, 800, legacy_header_established=True)
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]), 7)
        self.assertEqual(audits[0]["layout_version"], "legacy-all-ongoing-nine-column-v1")

    def test_legacy_continuation_accepts_8_column_without_header(self):
        table = FakeTable([["Sector", "2"] + ["value"] * 6])
        data, index, audits = _select_table6_candidate([table], 1, 600, 800, legacy_header_established=True)
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]), 8)
        self.assertEqual(audits[0]["layout_version"], "legacy-all-ongoing-nine-column-v1")

    def test_legacy_continuation_accepts_9_column_without_header(self):
        table = FakeTable([["State", "Sector", "3"] + ["value"] * 6])
        data, index, audits = _select_table6_candidate([table], 1, 600, 800, legacy_header_established=True)
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]), 9)
        self.assertEqual(audits[0]["layout_version"], "legacy-all-ongoing-nine-column-v1")

    def test_legacy_continuation_without_established_header_fails_closed(self):
        table_7 = FakeTable([["1"] + ["value"] * 6])
        with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
            _select_table6_candidate([table_7], 1, 600, 800, legacy_header_established=False)
        table_8 = FakeTable([["Sector", "1"] + ["value"] * 6])
        with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
            _select_table6_candidate([table_8], 1, 600, 800, legacy_header_established=False)

    def test_multiline_group_fragment_merging(self):
        from src.extraction.pipeline import _merge_legacy_group_fragment
        merged = _merge_legacy_group_fragment("HEALTH AND", "FAMILY WELFARE")
        self.assertEqual(merged, "HEALTH AND FAMILY WELFARE")
        merged_tele = _merge_legacy_group_fragment("TELECOMMUN", "ICATIONS")
        self.assertEqual(merged_tele, "TELECOMMUN ICATIONS")
        # Existing complete label not overwritten by duplicate fragment
        self.assertEqual(_merge_legacy_group_fragment("ANDHRA PRADESH", "ANDHRA"), "ANDHRA PRADESH")

    def test_jan_feb_mar_2024_select_by_own_milestones_signature(self):
        cases = (
            ("data/raw/2024/FR_jan_2024.pdf", 96),
            ("data/raw/2024/FR_feb_2024.pdf", 104),
            ("data/raw/2024/FR_mar_2024.pdf", 104),
        )
        for path, page_number in cases:
            with self.subTest(path=path):
                with pdfplumber.open(self.root / path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(pdf.pages[page_number - 1], page_number)
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
                header_index = 1 if "detail" in (selected[0][0] or "").lower() else 0
                self.assertEqual(len(selected[header_index]), 9)
                self.assertIn("si.no", selected[header_index][0].lower())

    def test_october_november_2023_select_by_own_milestones_signature(self):
        cases = (
            ("data/raw/2023/FR_oct_2023.pdf", 92),
            ("data/raw/2023/FR_nov_2023.pdf", 417),
        )
        for path, page_number in cases:
            with self.subTest(path=path):
                with pdfplumber.open(self.root / path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(
                        pdf.pages[page_number - 1], page_number
                    )
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
                self.assertEqual(len(selected[1]), 9)
                self.assertIn("si.no", selected[1][0].lower())

    def test_july_2023_footer_page_number_does_not_corrupt_bottom_date(self):
        with pdfplumber.open(self.root / "data/raw/2023/FR_july1_2023.pdf") as pdf:
            selected, _, _, _, _ = _locate_table6_candidate(pdf.pages[107], 108)
        row = next(row for row in selected if row[0] == "13")
        self.assertEqual(row[4], "9/2021")

    def test_july_august_september_2023_select_by_milestones_signature(self):
        cases = (
            ("data/raw/2023/FR_july1_2023.pdf", 108),
            ("data/raw/2023/FR_august_2023.pdf", 118),
            ("data/raw/2023/FR_sept_2023.pdf", 89),
        )
        for path, page_number in cases:
            with self.subTest(path=path):
                with pdfplumber.open(self.root / path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(
                        pdf.pages[page_number - 1], page_number
                    )
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
                self.assertEqual(len(selected[1]), 9)

    def test_april_may_june_2023_select_by_milestones_signature(self):
        cases = (
            ("data/raw/2023/FR_APril_2023.pdf", 114),
            ("data/raw/2023/FR_may_2023.pdf", 106),
            ("data/raw/2023/FR_june_2023.pdf", 107),
        )
        for path, page_number in cases:
            with self.subTest(path=path):
                with pdfplumber.open(self.root / path) as pdf:
                    selected, _, _, audits, _ = _locate_table6_candidate(
                        pdf.pages[page_number - 1], page_number
                    )
                matching = [audit for audit in audits if audit["matches_table6_signature"]]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
                self.assertEqual(len(selected[1]), 9)

    def test_detail_milestones_continuation_requires_established_header(self):
        with pdfplumber.open(self.root / "data/raw/2024/FR_jan_2024.pdf") as pdf:
            page = pdf.pages[96]  # Page 97 (continuation)
            with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
                _locate_table6_candidate(page, 97, legacy_header_established=False)
            selected, _, _, audits, _ = _locate_table6_candidate(page, 97, legacy_header_established=LEGACY_DETAIL_MILESTONES_LAYOUT)
        matching = [audit for audit in audits if audit["matches_table6_signature"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
        self.assertEqual(len(selected[0]), 7)

    def test_detail_milestones_final_identity_fragment_requires_established_header(self):
        with pdfplumber.open(self.root / "data/raw/2023/FR_oct_2023.pdf") as pdf:
            page = pdf.pages[214]  # Page 215: final identity suffix and total only.
            with self.assertRaisesRegex(TableCandidateSelectionError, "found 0"):
                _locate_table6_candidate(page, 215, legacy_header_established=False)
            selected, _, _, audits, _ = _locate_table6_candidate(
                page,
                215,
                legacy_header_established=LEGACY_DETAIL_MILESTONES_LAYOUT,
            )
        matching = [audit for audit in audits if audit["matches_table6_signature"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["layout_version"], LEGACY_DETAIL_MILESTONES_LAYOUT)
        self.assertEqual(matching[0]["project_row_count"], 0)
        self.assertEqual(matching[0]["detail_identity_continuation_rows"], 1)
        self.assertIn("[N30000004]", selected[0][1])


if __name__ == "__main__":
    unittest.main()
