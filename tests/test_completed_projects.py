"""Regression and unit tests for Table 3: Completed Projects extraction."""

import csv
from pathlib import Path
import unittest

from src.extraction.completed_projects import (
    COMPLETED_FIELDS,
    LAYOUT_LEGACY_SIX_COLUMN,
    LAYOUT_SEVEN_COLUMN,
    LAYOUT_TABLE2_LEGACY_FIVE_COLUMN,
    SchemaChangeDetected,
    TableCandidateSelectionError,
    classify_table2_header,
    classify_table3_header,
    detect_report_month,
    extract_completed_projects_from_pdf,
    is_table2_page,
    is_table3_page,
    parse_cost_number,
    parse_legacy_composite_cell,
    parse_month_string,
    parse_seven_column_composite_cell,
    parse_table2_composite_cell,
)
from src.validation.completed_projects import (
    EXPECTED_MONTHLY_ROW_COUNTS,
    validate_completed_csv,
    validate_completed_records,
)


class CompletedProjectsTests(unittest.TestCase):
    """Test suite for Table 3 extraction, parsing, and validation."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parent.parent
        cls.raw_dir = cls.root / "data" / "raw"
        cls.output_csv = cls.root / "data" / "processed" / "projects_completed.csv"

    def test_semantic_page_detection(self):
        """Verify semantic identification of Table 3 Completed Projects pages and rejection of others."""
        # Legacy completed page
        legacy_txt = "MOSPI_ (April 2025) _FR_ Central Sector Projects cost Rs. 150Cr and above Table:-3. Project List: Completed during April 2025"
        self.assertTrue(is_table3_page(legacy_txt))

        # 7-column completed page
        seven_txt = "Completed Projects During Month SEPTEMBER 2025 Actual Date of Completion"
        self.assertTrue(is_table3_page(seven_txt))

        # North-Eastern ongoing table (July/August 2025 Table 3) must be rejected
        ne_txt = "Table 3: Ongoing Projects North Eastern Region"
        self.assertFalse(is_table3_page(ne_txt))

        ne_txt2 = "Ongoing Projects of North-East Region"
        self.assertFalse(is_table3_page(ne_txt2))

        # General ongoing project table must be rejected
        ongoing_txt = "All Ongoing Projects as of September 2025"
        self.assertFalse(is_table3_page(ongoing_txt))

    def test_header_classification(self):
        """Test positional header matching against verified signatures and rejection of invalid headers."""
        legacy_hdr = [
            "Sector",
            "Sl. No.",
            "Project Name\n(Agency Name)\n(Project Code)\n(State Name)",
            "Original\nCost\nin Rs. Crore",
            "Date of Commissioning\nOriginal\n(MM/YYYY)",
            "Cumulative\nExpenditure\nin Rs. Crore",
        ]
        layout, failures = classify_table3_header(legacy_hdr)
        self.assertEqual(layout, LAYOUT_LEGACY_SIX_COLUMN)
        self.assertEqual(failures, [])

        seven_hdr = [
            "Sl.No",
            "Project Name (Agency) (Project Code)",
            "State",
            "Date of Approval\n(Start Date)\nMM/YYYY",
            "Actual Date of Completion\n(Orignal/Target DoC)\n(Revised DoC)\nMM/YYYY",
            "Orignal Cost\nRevised Cost\nin Rs. Crore",
            "Cumulative\nExpenditure\nin Rs. Crore",
        ]
        layout, failures = classify_table3_header(seven_hdr)
        self.assertEqual(layout, LAYOUT_SEVEN_COLUMN)
        self.assertEqual(failures, [])

        jun2026_hdr = [
            "Sl.No",
            "Project Name (Agency) (Project Code)",
            "State",
            "Date of Approval\n(Start Date)\nMM/YYYY",
            "(Orignal/Target DoC)\n(Revised DoC)\nMM/YYYY",
            "Orignal Cost\nRevised Cost\nin Rs. Crore",
            "Cumulative\nExpenditure\nin Rs. Crore",
        ]
        layout, failures = classify_table3_header(jun2026_hdr)
        self.assertEqual(layout, LAYOUT_SEVEN_COLUMN)
        self.assertEqual(failures, [])

        # Unsupported 5-column header
        bad_hdr = ["Sl.No", "Project", "Cost", "Exp", "Progress"]
        layout, failures = classify_table3_header(bad_hdr)
        self.assertIsNone(layout)
        self.assertTrue(any("unsupported column count" in f for f in failures))

    def test_legacy_composite_cell_parsing(self):
        """Test parsing of legacy 4-element composite cells."""
        cell = (
            "UPGRADATION OF PASSENGER TERMINAL BUILDING\n"
            "AND AIRSIDE FACILITIES AT TIRUCHIRAPALLI\n"
            "INTERNATIONAL AI\n"
            "(AAI)\n"
            "(N04000075)\n"
            "(TAMIL NADU)"
        )
        name, agency, code, state = parse_legacy_composite_cell(cell)
        self.assertEqual(code, "N04000075")
        self.assertEqual(agency, "AAI")
        self.assertEqual(state, "TAMIL NADU")
        self.assertEqual(
            name,
            "UPGRADATION OF PASSENGER TERMINAL BUILDING AND AIRSIDE FACILITIES AT TIRUCHIRAPALLI INTERNATIONAL AI",
        )

        # 9-digit numeric legacy code
        cell9 = "PROJECT FOO BAR\n(NHAI)\n(123456789)\n(KARNATAKA)"
        name9, agency9, code9, state9 = parse_legacy_composite_cell(cell9)
        self.assertEqual(code9, "123456789")
        self.assertEqual(agency9, "NHAI")
        self.assertEqual(state9, "KARNATAKA")

        # Missing code must fail closed
        with self.assertRaises(SchemaChangeDetected):
            parse_legacy_composite_cell("PROJECT WITHOUT CODE\n(NHAI)\n(KERALA)")

    def test_seven_column_composite_cell_parsing(self):
        """Test parsing of seven-column 3-element composite cells."""
        cell = (
            "IoE Projects [Civil Works], IIT Kharagpur\n"
            "(Indian Institute of Technology, Kharagpur)\n"
            "609041"
        )
        name, agency, code = parse_seven_column_composite_cell(cell)
        self.assertEqual(code, "609041")
        self.assertEqual(agency, "Indian Institute of Technology, Kharagpur")
        self.assertEqual(name, "IoE Projects [Civil Works], IIT Kharagpur")

        # Agency with brackets inside parens
        cell_bracket = (
            "Goa Airport Terminal Building Extension Project\n"
            "(Airport Authority of India [AAI])\n"
            "701105"
        )
        name_b, agency_b, code_b = parse_seven_column_composite_cell(cell_bracket)
        self.assertEqual(code_b, "701105")
        self.assertEqual(agency_b, "Airport Authority of India [AAI]")
        self.assertEqual(name_b, "Goa Airport Terminal Building Extension Project")

        # Missing 6-digit code must fail closed
        with self.assertRaises(SchemaChangeDetected):
            parse_seven_column_composite_cell("PROJECT WITHOUT CODE\n(AAI)")

    def test_date_and_cost_parsing(self):
        """Test date and cost parsing helpers."""
        self.assertEqual(parse_month_string("08/2025"), "2025-08")
        self.assertEqual(parse_month_string("(03/2023)"), "2023-03")
        self.assertIsNone(parse_month_string("N.A."))
        self.assertIsNone(parse_month_string("(-)"))
        self.assertIsNone(parse_month_string(""))

        self.assertEqual(parse_cost_number("287.2"), 287.2)
        self.assertEqual(parse_cost_number("1,084.94"), 1084.94)
        self.assertEqual(parse_cost_number("(2465.68)"), 2465.68)
        self.assertIsNone(parse_cost_number("(-)"))
        self.assertIsNone(parse_cost_number("-"))

    def test_absence_handling_july_and_august_2025(self):
        """Verify July and August 2025 cleanly report absence of Table 3 Completed Projects."""
        for m, pdf_name in [("2025-07", "FlashReport_July_2025.pdf"), ("2025-08", "FlashReport_August_2025.pdf")]:
            pdf_path = self.raw_dir / "2025" / pdf_name
            if pdf_path.exists():
                records, manifest = extract_completed_projects_from_pdf(pdf_path)
                self.assertEqual(len(records), 0)
                self.assertFalse(manifest["table3_present"])
                self.assertEqual(manifest["row_count"], 0)

    def test_semantic_table2_page_detection(self):
        """Verify semantic identification of Table 2 Completed Projects pages and rejection of others."""
        t2_txt = "Month wise List of Completed Projects Costing Rs. 150 crore and above during 2023-2024"
        self.assertTrue(is_table2_page(t2_txt))

        # Ongoing projects or deleted projects pages must be rejected
        ongoing_txt = "All Ongoing Projects as of April 2023"
        self.assertFalse(is_table2_page(ongoing_txt))

        deleted_txt = "List of Deleted Projects during 2023-2024"
        self.assertFalse(is_table2_page(deleted_txt))

    def test_table2_header_classification(self):
        """Test Table 2 5-column positional header matching and rejection of invalid headers."""
        valid_hdr = [
            "Sl. No",
            "Project Name",
            "Original Cost\n(Rs. crore)",
            "Original Date of\ncommissioning",
            "Cumulative\nExpenditure\n(Rs. crore)",
        ]
        layout, failures = classify_table2_header(valid_hdr)
        self.assertEqual(layout, LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
        self.assertEqual(failures, [])

        bad_hdr = ["Sl. No", "Project Name", "Cost", "Exp", "Progress"]
        layout, failures = classify_table2_header(bad_hdr)
        self.assertIsNone(layout)
        self.assertTrue(len(failures) > 0)

    def test_parse_table2_composite_cell(self):
        """Test parsing of composite project cells from Table 2 legacy 5-column layout."""
        cell1 = "Hindustan Petroleum Corporation Ltd. (Petroleum)\n- [N16000282]"
        name, agency, code = parse_table2_composite_cell(cell1)
        self.assertEqual(name, "Hindustan Petroleum Corporation Ltd.")
        self.assertEqual(agency, "Petroleum")
        self.assertEqual(code, "N16000282")

        # Cell with parentheses within project name
        cell2 = "Flyover (Phase 1) Construction (PWD) - [N24000866]"
        name, agency, code = parse_table2_composite_cell(cell2)
        self.assertEqual(name, "Flyover (Phase 1) Construction")
        self.assertEqual(agency, "PWD")
        self.assertEqual(code, "N24000866")

        # Cell with 9-digit numeric legacy code
        cell3 = "Khurda Road-Barang 3rd Line (BBS-BRAG) (ECOR) - [220100164]"
        name, agency, code = parse_table2_composite_cell(cell3)
        self.assertEqual(name, "Khurda Road-Barang 3rd Line (BBS-BRAG)")
        self.assertEqual(agency, "ECOR")
        self.assertEqual(code, "220100164")

    def test_output_dataset_integrity(self):
        """Verify generated projects_completed.csv passes all structural and quality checks."""
        self.assertTrue(self.output_csv.exists(), f"Missing {self.output_csv}")
        summary = validate_completed_csv(self.output_csv)

        # Total records must match 876 exactly (811 baseline + 65 Batch 4)
        self.assertEqual(summary["total_records"], 876)
        self.assertEqual(summary["unique_projects"], 876)
        self.assertEqual(summary["missing_project_codes"], 0)
        self.assertEqual(summary["duplicate_keys"], 0)
        self.assertTrue(summary["serial_continuity_all_months"])
        self.assertEqual(summary["warnings_count"], 0)

        # Monthly row counts must match expected counts exactly
        for month, expected_count in EXPECTED_MONTHLY_ROW_COUNTS.items():
            if expected_count > 0:
                self.assertEqual(summary["rows_by_month"].get(month), expected_count, f"Mismatch in {month}")

        # Check schema header matches COMPLETED_FIELDS
        with self.output_csv.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
        self.assertEqual(header, COMPLETED_FIELDS)

    def test_historical_legacy_extraction(self):
        """Test extraction of historical legacy reports with sector margin headings and NER project names."""
        july_pdf = self.raw_dir / "2024" / "July_Part-II.pdf"
        if july_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(july_pdf)
            self.assertEqual(len(records), 21)
            self.assertEqual(manifest["layout_version"], LAYOUT_LEGACY_SIX_COLUMN)
            self.assertEqual(records[0]["sector"], "POWER")
            self.assertEqual(records[13]["sector"], "ROAD TRANSPORT AND HIGHWAYS")
            self.assertEqual(records[20]["sector"], "STEEL")

        dec_pdf = self.raw_dir / "2024" / "December.pdf"
        if dec_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(dec_pdf)
            self.assertEqual(len(records), 22)
            self.assertEqual(manifest["layout_version"], LAYOUT_LEGACY_SIX_COLUMN)
            self.assertEqual(records[6]["project_code"], "N18000316")
            self.assertIn("NORTH EASTERN REGION", records[6]["project_name"])

    def test_batch1_table2_extraction(self):
        """Test extraction of Batch 1 reports (April, May, June 2023) using Table 2 adapter."""
        apr_pdf = self.raw_dir / "2023" / "FR_APril_2023.pdf"
        if apr_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(apr_pdf)
            self.assertEqual(len(records), 20)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 1)
            self.assertEqual(records[-1]["source_serial_number"], 20)
            self.assertEqual(records[0]["project_code"], "N16000282")
            self.assertEqual(records[0]["sector"], "PETROLEUM")

        may_pdf = self.raw_dir / "2023" / "FR_may_2023.pdf"
        if may_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(may_pdf)
            self.assertEqual(len(records), 10)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 21)
            self.assertEqual(records[-1]["source_serial_number"], 30)

        jun_pdf = self.raw_dir / "2023" / "FR_june_2023.pdf"
        if jun_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(jun_pdf)
            self.assertEqual(len(records), 54)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 31)
            self.assertEqual(records[-1]["source_serial_number"], 84)

    def test_batch2_table2_extraction(self):
        """Test extraction of Batch 2 reports (July, August, September 2023) using Table 2 adapter."""
        jul_pdf = self.raw_dir / "2023" / "FR_july1_2023.pdf"
        if jul_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(jul_pdf)
            self.assertEqual(len(records), 7)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 85)
            self.assertEqual(records[-1]["source_serial_number"], 91)
            self.assertEqual(records[0]["project_code"], "N16000272")
            self.assertEqual(records[0]["sector"], "PETROLEUM")

        aug_pdf = self.raw_dir / "2023" / "FR_august_2023.pdf"
        if aug_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(aug_pdf)
            self.assertEqual(len(records), 15)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 92)
            self.assertEqual(records[-1]["source_serial_number"], 106)
            self.assertEqual(records[0]["project_code"], "N16000342")
            self.assertEqual(records[0]["sector"], "PETROLEUM")

        sep_pdf = self.raw_dir / "2023" / "FR_sept_2023.pdf"
        if sep_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(sep_pdf)
            self.assertEqual(len(records), 48)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 107)
            self.assertEqual(records[-1]["source_serial_number"], 154)
            self.assertEqual(records[0]["project_code"], "N12000086")
            self.assertEqual(records[0]["sector"], "STEEL")

    def test_batch3_table2_extraction(self):
        """Test extraction of Batch 3 reports (October, November, December 2023) using Table 2 adapter."""
        oct_pdf = self.raw_dir / "2023" / "FR_oct_2023.pdf"
        if oct_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(oct_pdf)
            self.assertEqual(len(records), 29)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 155)
            self.assertEqual(records[-1]["source_serial_number"], 183)
            self.assertEqual(records[0]["project_code"], "N16000345")
            self.assertEqual(records[0]["sector"], "PETROLEUM")
            self.assertEqual(records[-1]["project_code"], "N28000120")
            self.assertEqual(records[-1]["sector"], "DEPARTMENT OF HIGHER EDUCATION")

        nov_pdf = self.raw_dir / "2023" / "FR_nov_2023.pdf"
        if nov_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(nov_pdf)
            self.assertEqual(len(records), 11)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 184)
            self.assertEqual(records[-1]["source_serial_number"], 194)
            self.assertEqual(records[0]["project_code"], "N06000225")
            self.assertEqual(records[0]["sector"], "COAL")
            self.assertEqual(records[-1]["project_code"], "N24001365")
            self.assertEqual(records[-1]["sector"], "ROAD TRANSPORT AND HIGHWAYS")

        dec_pdf = self.raw_dir / "2023" / "FR_dec_2023.pdf"
        if dec_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(dec_pdf)
            self.assertEqual(len(records), 0)
            self.assertFalse(manifest.get("completed_present", manifest.get("table3_present")))

    def test_batch4_table2_extraction(self):
        """Test extraction of Batch 4 reports (January, February, March 2024) using Table 2 adapter."""
        jan_pdf = self.raw_dir / "2023" / "FR_jan_2024.pdf"
        if jan_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(jan_pdf)
            self.assertEqual(len(records), 13)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 217)
            self.assertEqual(records[-1]["source_serial_number"], 229)
            self.assertEqual(records[0]["project_code"], "N06000095")
            self.assertEqual(records[0]["sector"], "COAL")
            self.assertEqual(records[-1]["project_code"], "N24001776")
            self.assertEqual(records[-1]["sector"], "ROAD TRANSPORT AND HIGHWAYS")

        feb_pdf = self.raw_dir / "2023" / "FR_feb_2024.pdf"
        if feb_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(feb_pdf)
            self.assertEqual(len(records), 20)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 230)
            self.assertEqual(records[-1]["source_serial_number"], 249)
            self.assertEqual(records[0]["project_code"], "N16000321")
            self.assertEqual(records[0]["sector"], "PETROLEUM")
            self.assertEqual(records[-1]["project_code"], "N24001760")
            self.assertEqual(records[-1]["sector"], "ROAD TRANSPORT AND HIGHWAYS")

        mar_pdf = self.raw_dir / "2023" / "FR_mar_2024.pdf"
        if mar_pdf.exists():
            records, manifest = extract_completed_projects_from_pdf(mar_pdf)
            self.assertEqual(len(records), 32)
            self.assertEqual(manifest["layout_version"], LAYOUT_TABLE2_LEGACY_FIVE_COLUMN)
            self.assertEqual(records[0]["source_serial_number"], 250)
            self.assertEqual(records[-1]["source_serial_number"], 281)
            self.assertEqual(records[0]["project_code"], "N16000249")
            self.assertEqual(records[0]["sector"], "PETROLEUM")
            self.assertEqual(records[-1]["project_code"], "N24001497")
            self.assertEqual(records[-1]["sector"], "ROAD TRANSPORT AND HIGHWAYS")


if __name__ == "__main__":
    unittest.main()
