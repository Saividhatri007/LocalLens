"""Smoke tests for LocalLens extraction and export helpers."""

import shutil
import unittest
from pathlib import Path

import locallens_core as core


PROJECT_DIR = Path(__file__).parent
SAMPLE_IMAGE = PROJECT_DIR / "locallens_sample_form.png"
TESSERACT_PATH = getattr(getattr(core.pytesseract, "pytesseract", None), "tesseract_cmd", "")
OCR_AVAILABLE = (
    core.Image is not None
    and core.pytesseract is not None
    and (shutil.which("tesseract") is not None or Path(TESSERACT_PATH).exists())
)


class LocalLensCoreTests(unittest.TestCase):
    def test_text_pdf_extracts_expected_fields(self):
        if core.fitz is None:
            self.skipTest("PyMuPDF is not installed")
        document = core.fitz.open()
        page = document.new_page()
        for index, line in enumerate((
            "Full Name: Avery Sample",
            "Email: avery.sample@example.test",
            "Phone: +1 555 010 2048",
            "Date of Birth: 14/08/2002",
            "ID Number: DEMO-482913",
        )):
            page.insert_text((72, 72 + index * 20), line)

        text, error = core.extract_pdf(document.tobytes())
        self.assertEqual(error, "")
        self.assertEqual(core.find_fields(text), {
            "Name": "Avery Sample",
            "Phone": "+1 555 010 2048",
            "Date": "14/08/2002",
            "ID Number": "DEMO-482913",
            "Email": "avery.sample@example.test",
        })

    @unittest.skipUnless(OCR_AVAILABLE, "Local Tesseract OCR is not installed")
    def test_scanned_pdf_uses_local_ocr(self):
        if core.fitz is None:
            self.skipTest("PyMuPDF is not installed")
        document = core.fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=SAMPLE_IMAGE.read_bytes())

        text, error = core.extract_pdf(document.tobytes())
        self.assertEqual(error, "")
        fields = core.find_fields(text)
        self.assertEqual(fields.get("Name"), "Avery Sample")
        self.assertEqual(fields.get("Email"), "avery.sample@example.test")
        self.assertEqual(fields.get("Date"), "14/08/2002")
        self.assertEqual(fields.get("ID Number"), "DEMO-482913")

    def test_ocr_style_split_labels_and_values(self):
        text = """SAMPLE FORM
Full Name
Avery Sample
Email
avery.sample@example.test
Phone
+1 555 010 2048
Date of Birth
14/08/2002
ID Number
DEMO-482913"""
        fields = core.find_fields(text)
        self.assertEqual(fields["Name"], "Avery Sample")
        self.assertEqual(fields["Phone"], "+1 555 010 2048")
        self.assertEqual(fields["Date"], "14/08/2002")
        self.assertEqual(fields["ID Number"], "DEMO-482913")
        self.assertEqual(fields["Email"], "avery.sample@example.test")

    def test_missing_value_does_not_consume_next_field(self):
        fields = core.find_fields("Full Name\nEmail: avery.sample@example.test")
        self.assertNotIn("Name", fields)
        self.assertEqual(fields["Email"], "avery.sample@example.test")

    def test_sample_image_runs_through_local_ocr(self):
        if not OCR_AVAILABLE:
            self.skipTest("Local Tesseract OCR is not installed")
        text, error = core.ocr_image(SAMPLE_IMAGE.read_bytes())
        self.assertEqual(error, "")
        fields = core.find_fields(text)
        self.assertEqual(fields.get("Name"), "Avery Sample")
        self.assertEqual(fields.get("Email"), "avery.sample@example.test")
        self.assertEqual(fields.get("Date"), "14/08/2002")
        self.assertEqual(fields.get("ID Number"), "DEMO-482913")
        self.assertEqual("".join(filter(str.isdigit, fields.get("Phone", ""))), "15550102048")

    @unittest.skipUnless(OCR_AVAILABLE, "Local Tesseract OCR is not installed")
    def test_source_highlights_locate_sample_values(self):
        text, error = core.ocr_image(SAMPLE_IMAGE.read_bytes())
        self.assertEqual(error, "")
        fields = core.find_fields(text)
        preview, highlighted = core.highlight_image_preview(SAMPLE_IMAGE.read_bytes(), fields)
        self.assertIsNotNone(preview)
        self.assertEqual(set(highlighted), set(fields))

    @unittest.skipUnless(OCR_AVAILABLE, "Local Tesseract OCR is not installed")
    def test_image_redaction_covers_selected_values(self):
        selected = {"Name": "Avery Sample", "Email": "avery.sample@example.test"}
        redacted, matched, missing = core.redact_image_copy(SAMPLE_IMAGE.read_bytes(), selected)
        self.assertEqual(missing, [])
        self.assertEqual(set(matched), set(selected))
        text, error = core.ocr_image(redacted)
        self.assertEqual(error, "")
        self.assertNotIn("Avery Sample", text)
        self.assertNotIn("avery.sample@example.test", text)

    @unittest.skipUnless(OCR_AVAILABLE, "Local Tesseract OCR is not installed")
    def test_scanned_pdf_redaction_creates_flattened_copy(self):
        if core.fitz is None:
            self.skipTest("PyMuPDF is not installed")
        source = core.fitz.open()
        page = source.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=SAMPLE_IMAGE.read_bytes())
        selected = {"Name": "Avery Sample", "Email": "avery.sample@example.test"}
        redacted, matched, missing = core.redact_pdf_copy(source.tobytes(), selected)
        self.assertEqual(missing, [])
        self.assertEqual(set(matched), set(selected))
        flattened = core.fitz.open(stream=redacted, filetype="pdf")
        self.assertEqual(flattened.page_count, 1)
        self.assertEqual(flattened[0].get_text("text").strip(), "")
        remaining_text, error = core.extract_pdf(redacted)
        self.assertEqual(error, "")
        self.assertNotIn("Avery Sample", remaining_text)
        self.assertNotIn("avery.sample@example.test", remaining_text)

    def test_csv_export_contains_reviewed_fields(self):
        csv_data = core.csv_bytes([{"Field": "Name", "Value": "Avery Sample"}]).decode("utf-8")
        self.assertIn("Field,Value", csv_data)
        self.assertIn("Name,Avery Sample", csv_data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
