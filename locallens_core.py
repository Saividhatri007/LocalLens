"""Local document extraction and review helpers used by the LocalLens app."""

import csv
import io
import re
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

if pytesseract is not None:
    # The Windows installer may not add Tesseract to PATH. Check its usual locations.
    for tesseract_path in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ):
        if tesseract_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
            break


def extract_pdf(data: bytes) -> tuple[str, str]:
    if fitz is None:
        return "", "Install PyMuPDF to read PDF files."
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text("text") for page in doc).strip()
    return text, ""


def pdf_first_page_preview(data: bytes):
    if fitz is None:
        return None
    document = fitz.open(stream=data, filetype="pdf")
    if not document:
        return None
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
    return pixmap.tobytes("png")


def ocr_image(data: bytes) -> tuple[str, str]:
    if Image is None or pytesseract is None:
        return "", "Image OCR needs Pillow and pytesseract. Install the listed packages and the Tesseract OCR application."
    try:
        image = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(image).strip(), ""
    except Exception as exc:
        return "", f"OCR could not read this image: {exc}"


def find_fields(text: str) -> dict[str, str]:
    found = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # OCR often places a field label and its value on separate lines, with
    # punctuation omitted. Accept both that layout and label: value text.
    field_labels = {
        "Name": r"full\s+name|name",
        "Phone": r"phone|mobile|contact",
        "Date": r"date\s+of\s+birth|dob|date",
        "ID Number": r"id\s*(?:number|no)?|document\s*(?:number|no)",
    }
    for output_label, label_pattern in field_labels.items():
        for index, line in enumerate(lines):
            match = re.match(rf"^\s*(?:{label_pattern})\s*[:#\-]?\s*(.*?)\s*$", line, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            if not value and index + 1 < len(lines):
                candidate = lines[index + 1]
                next_line_is_label = re.match(
                    r"^(?:full\s+name|name|email|phone|mobile|contact|date(?:\s+of\s+birth)?|dob|id\s*(?:number|no)?|document\s*(?:number|no))\b\s*[:#\-]?",
                    candidate,
                    re.IGNORECASE,
                )
                if not next_line_is_label:
                    value = candidate
            if output_label == "Phone" and value:
                value = re.sub(r"[^+()0-9 .-]", "", value).strip()
                if len(re.sub(r"\D", "", value)) < 7:
                    continue
            elif output_label == "Date" and not re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", value):
                continue
            elif output_label == "ID Number" and not re.search(r"[A-Z0-9-]{5,}", value, re.IGNORECASE):
                continue
            if value:
                found[output_label] = value
                break

    email = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
    if email:
        found["Email"] = email.group(0)
    return found


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["Field", "Value"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def value_status(label: str, value: str) -> str:
    """A format hint only; it is not a measure of OCR confidence."""
    if not value.strip():
        return "Needs review"
    if label == "Email":
        return "Format looks OK" if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value) else "Check format"
    if label == "Phone":
        return "Format looks OK" if len(re.sub(r"\D", "", value)) >= 7 else "Check format"
    if label == "Date":
        return "Format looks OK" if re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", value) else "Check format"
    if label == "ID Number":
        return "Format looks OK" if len(value) >= 5 else "Check format"
    return "Review against source"


def source_evidence(text: str, value: str) -> str:
    """Return the nearby extracted lines for a value, when available."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    target = value.casefold().strip()
    for index, line in enumerate(lines):
        if target and target in line.casefold():
            start, end = max(0, index - 1), min(len(lines), index + 2)
            return "\n".join(lines[start:end])
    return "Source text wasn’t matched exactly. Check the value in the document preview."
