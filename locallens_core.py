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
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None

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


def pdf_page_count(data: bytes) -> int:
    """Return the number of pages in a PDF, or raise a useful error."""
    if fitz is None:
        raise RuntimeError("Install PyMuPDF to read PDF files.")
    document = fitz.open(stream=data, filetype="pdf")
    try:
        count = len(document)
        if count < 1:
            raise ValueError("This PDF has no pages to read.")
        return count
    finally:
        document.close()


def extract_pdf(data: bytes, selected_pages: list[int] | None = None) -> tuple[str, str]:
    """Extract selected one-based PDF pages; None means every page."""
    if fitz is None:
        return "", "Install PyMuPDF to read PDF files."
    doc = fitz.open(stream=data, filetype="pdf")
    page_numbers = list(range(1, len(doc) + 1)) if selected_pages is None else sorted(set(selected_pages))
    if not page_numbers or any(number < 1 or number > len(doc) for number in page_numbers):
        doc.close()
        return "", "Choose one or more valid PDF pages to read."
    extracted_pages = []
    for page_number in page_numbers:
        page = doc[page_number - 1]
        page_text = page.get_text("text").strip()
        if not page_text and Image is not None and pytesseract is not None:
            try:
                pixmap = page.get_pixmap(dpi=200, alpha=False)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                page_text = pytesseract.image_to_string(image, lang="eng").strip()
            except Exception as exc:
                if not extracted_pages:
                    return "", f"Local OCR could not read scanned PDF page {page_number}: {exc}"
        extracted_pages.append(f"[PDF page {page_number}]\n{page_text}" if page_text else "")

    text = "\n\n".join(page for page in extracted_pages if page).strip()
    if not text and any(not doc[number - 1].get_text("text").strip() for number in page_numbers):
        if Image is None or pytesseract is None:
            return "", "This looks like a scanned PDF. Install Tesseract OCR to read scanned PDF pages locally."
        return "", "No text could be read from this PDF. Check the scan quality and try again."
    return text, ""


def pdf_first_page_preview(data: bytes):
    if fitz is None:
        return None
    document = fitz.open(stream=data, filetype="pdf")
    if not document:
        return None
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
    return pixmap.tobytes("png")


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _image_ocr_groups(image):
    """Read and group OCR word boxes once so the session can reuse them."""
    if Image is None or pytesseract is None:
        return []
    data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)
    groups = {}
    for i, word in enumerate(data["text"]):
        token = _normalized(word)
        if not token:
            continue
        line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(line_key, []).append((
            int(data["word_num"][i]), token,
            int(data["left"][i]), int(data["top"][i]),
            int(data["left"][i] + data["width"][i]), int(data["top"][i] + data["height"][i]),
        ))

    return [sorted(words, key=lambda word: word[0]) for words in groups.values()]


def _match_values_to_ocr_groups(groups, values: dict[str, str]):
    matches = {label: [] for label in values}
    for words in groups:
        words.sort(key=lambda word: word[0])
        for label, value in values.items():
            target = _normalized(value)
            if len(target) < 3:
                continue
            for start in range(len(words)):
                combined = ""
                for end in range(start, len(words)):
                    combined += words[end][1]
                    if combined == target:
                        segment = words[start:end + 1]
                        matches[label].append((
                            min(word[2] for word in segment), min(word[3] for word in segment),
                            max(word[4] for word in segment), max(word[5] for word in segment),
                        ))
                        break
                    if len(combined) >= len(target) or not target.startswith(combined):
                        break
    return {label: boxes for label, boxes in matches.items() if boxes}


def _image_value_boxes(image, values: dict[str, str]) -> dict[str, list[tuple[int, int, int, int]]]:
    """Locate requested text using local OCR word boxes."""
    return _match_values_to_ocr_groups(_image_ocr_groups(image), values)


def _draw_highlights(image, matches: dict[str, list[tuple[int, int, int, int]]]):
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for boxes in matches.values():
        for left, top, right, bottom in boxes:
            draw.rectangle((left - 3, top - 3, right + 3, bottom + 3), fill=(245, 190, 74, 78), outline=(167, 103, 61, 230), width=2)
    return Image.alpha_composite(base, overlay).convert("RGB")


def _draw_redactions(image, matches: dict[str, list[tuple[int, int, int, int]]]):
    output = image.convert("RGB")
    draw = ImageDraw.Draw(output)
    for boxes in matches.values():
        for left, top, right, bottom in boxes:
            draw.rectangle((max(0, left - 5), max(0, top - 5), right + 5, bottom + 5), fill="#111111")
    return output


def _png_bytes(image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def highlight_image_preview(data: bytes, values: dict[str, str]):
    if Image is None or pytesseract is None:
        return None, []
    image = Image.open(io.BytesIO(data)).convert("RGB")
    matches = _image_value_boxes(image, values)
    return _png_bytes(_draw_highlights(image, matches)), list(matches)


def prepare_image_preview(data: bytes):
    """Prepare reusable image and OCR data for one app session."""
    if Image is None:
        return None
    image = Image.open(io.BytesIO(data)).convert("RGB")
    return _png_bytes(image), _image_ocr_groups(image) if pytesseract is not None else []


def draw_prepared_preview(prepared, values: dict[str, str]):
    """Draw changed highlights without repeating OCR on the same preview."""
    if Image is None or not prepared:
        return None, []
    image_bytes, ocr_groups = prepared
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    matches = _match_values_to_ocr_groups(ocr_groups, values)
    return _png_bytes(_draw_highlights(image, matches)), list(matches)


def highlight_pdf_preview(data: bytes, values: dict[str, str]):
    if fitz is None or Image is None:
        return None, []
    document = fitz.open(stream=data, filetype="pdf")
    if not document:
        return None, []
    page_image = Image.open(io.BytesIO(document[0].get_pixmap(dpi=200, alpha=False).tobytes("png"))).convert("RGB")
    matches = _image_value_boxes(page_image, values) if pytesseract is not None else {}
    return _png_bytes(_draw_highlights(page_image, matches)), list(matches)


def highlight_pdf_page_previews(data: bytes, values: dict[str, str], page_numbers: list[int]):
    """Render selected one-based PDF pages with any locally matched values highlighted."""
    prepared = [prepare_pdf_page_preview(data, number) for number in page_numbers]
    return [draw_prepared_pdf_page(preview, values) for preview in prepared if preview]


def prepare_pdf_page_preview(data: bytes, page_number: int):
    """Render one PDF page and read its text-layer boxes for fast highlighting."""
    if fitz is None or Image is None:
        return None
    document = fitz.open(stream=data, filetype="pdf")
    try:
        if page_number < 1 or page_number > len(document):
            return None
        page = document[page_number - 1]
        page_image = Image.open(io.BytesIO(page.get_pixmap(dpi=160, alpha=False).tobytes("png"))).convert("RGB")
        scale_x = page_image.width / page.rect.width
        scale_y = page_image.height / page.rect.height
        groups = {}
        for word in page.get_text("words"):
            x0, y0, x1, y1, text, block_number, line_number, word_number = word
            token = _normalized(text)
            if token:
                groups.setdefault((block_number, line_number), []).append((
                    word_number, token,
                    int(x0 * scale_x), int(y0 * scale_y),
                    int(x1 * scale_x), int(y1 * scale_y),
                ))
        return page_number, _png_bytes(page_image), [sorted(words, key=lambda item: item[0]) for words in groups.values()]
    finally:
        document.close()


def draw_prepared_pdf_page(prepared, values: dict[str, str]):
    if Image is None or not prepared:
        return None
    page_number, image_bytes, ocr_groups = prepared
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    matches = _match_values_to_ocr_groups(ocr_groups, values)
    return page_number, _png_bytes(_draw_highlights(image, matches)), list(matches)


def redact_image_copy(data: bytes, values: dict[str, str]):
    if Image is None or pytesseract is None:
        return None, [], list(values)
    image = Image.open(io.BytesIO(data)).convert("RGB")
    matches = _image_value_boxes(image, values)
    missing = [label for label in values if label not in matches]
    if missing:
        return None, list(matches), missing
    return _png_bytes(_draw_redactions(image, matches)), list(matches), []


def redact_pdf_copy(data: bytes, values: dict[str, str]):
    """Create a flattened, image-only PDF with selected OCR matches blacked out."""
    if fitz is None or Image is None or pytesseract is None:
        return None, [], list(values)
    source = fitz.open(stream=data, filetype="pdf")
    output = fitz.open()
    found = set()
    for page in source:
        image = Image.open(io.BytesIO(page.get_pixmap(dpi=220, alpha=False).tobytes("png"))).convert("RGB")
        matches = _image_value_boxes(image, values)
        found.update(matches)
        redacted_image = _draw_redactions(image, matches)
        new_page = output.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=_png_bytes(redacted_image))
    missing = [label for label in values if label not in found]
    if missing:
        return None, sorted(found), missing
    return output.tobytes(), sorted(found), []


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
