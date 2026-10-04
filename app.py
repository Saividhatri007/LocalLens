import csv
import hashlib
import io
import json
import re
from pathlib import Path

import streamlit as st

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


st.set_page_config(page_title="LocalLens", page_icon="🔎", layout="wide")
st.markdown("""
<style>
  :root { --ink:#3e342f; --muted:#88786f; --panel:#fffdf9; --panel2:#f4ece3; --line:#e5d8ca; --gold:#b87860; --mint:#628b70; }
  .stApp { background: radial-gradient(ellipse at 50% -20%, #eee0d2 0%, #f7f3ed 58%); color:var(--ink); }
  [data-testid="stHeader"] { background:rgba(247,243,237,0); }
  [data-testid="stAppViewContainer"] .main .block-container { max-width:1320px; padding-top:2.4rem; padding-bottom:3rem; }
  h1,h2,h3 { color:var(--ink); letter-spacing:-.02em; }
  h2 { font-size:1.35rem; }
  .hero { padding:1.65rem 1.9rem; border:1px solid var(--line); border-radius:22px;
          background:linear-gradient(120deg,#f5e9dd,#eee0d3); margin-bottom:1rem; }
  .hero-row { display:flex; align-items:center; gap:1rem; }
  .hero-icon { width:54px; height:54px; border-radius:16px; display:flex; align-items:center; justify-content:center;
          background:#e9d3c2; font-size:1.8rem; }
  .eyebrow { color:#a8644d; font-size:.75rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
  .hero h1 { margin:.2rem 0; font-size:2.35rem; }
  .hero p { color:#66574f; margin:.45rem 0 0; }
  .privacy-note { color:var(--muted); font-size:.88rem; margin:.8rem 0 1.25rem; }
  .section-card { background:rgba(24,38,46,.82); border:1px solid var(--line); border-radius:18px; padding:1.15rem 1.25rem; }
  .section-kicker { color:var(--gold); text-transform:uppercase; letter-spacing:.11em; font-size:.72rem; font-weight:800; }
  .field-label { color:#c4cdd1; font-size:.82rem; font-weight:650; margin-bottom:.25rem; }
  .status-pill { display:inline-block; border-radius:99px; padding:.3rem .65rem; color:#4d755b;
          background:#e8f0e8; border:1px solid #ccdfce; font-size:.78rem; font-weight:700; }
  .stButton button, .stDownloadButton button { border-radius:10px; min-height:2.7rem; font-weight:700; }
  .stButton button { background:#f2e5da !important; color:#493a33 !important; border:1px solid #d8bba8 !important; }
  .stDownloadButton button { background:#f2e5da !important; color:#493a33 !important; border:1px solid #d8bba8 !important; }
  .stButton button[kind="primary"], .stDownloadButton button[kind="primary"] { background:#b87860 !important; color:#fffaf5 !important; border:0 !important; }
  [data-testid="stFileUploader"] { background:#fffdf9; border:1px solid #e5d8ca; border-radius:16px; padding:.7rem; }
  [data-testid="stFileUploaderDropzone"] { background:#eee0d5 !important; border:1px dashed #c8aa95 !important; border-radius:12px !important; }
  [data-testid="stFileUploaderDropzone"] button { background:#b87860 !important; color:#fffaf5 !important; border:0 !important; }
  [data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzone"] span { color:#5f514a !important; }
  div[data-testid="stAlert"] { background:#f0e5d9; border:1px solid #e2cbb9; border-radius:12px; color:#5b4940; }
  div[data-testid="stAlert"] p { color:#5b4940; }
  div[data-testid="stAlert"] svg { fill:#a8644d; }
  [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { background:#fffdf9; color:var(--ink); border-color:#d9c8b8; }
  div[data-testid="stVerticalBlockBorderWrapper"] { background:#eee0d5; border-radius:18px; border-color:#d8c0b0; }
  div[data-testid="stMetric"] { background:#fffdf9; padding:.9rem 1rem; border:1px solid var(--line); border-radius:14px; }
  div[data-testid="stMetricLabel"] { color:var(--muted) !important; }
  div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div { color:var(--ink) !important; font-family:inherit !important; font-size:1.2rem !important; font-weight:700 !important; line-height:1.35 !important; }
  hr { border-color:var(--line); }
  .stMarkdown, .stCaption, label, label p, [data-testid="stWidgetLabel"] p, [data-testid="stFileUploader"] { color:var(--ink) !important; }
  [data-testid="stCode"] { background:#f5ece3; border:1px solid #e5d8ca; border-radius:10px; }
  [data-testid="stCode"] pre, [data-testid="stCode"] code { color:#493a33 !important; }
  [data-testid="stExpander"] { background:#fffdf9; border:1px solid var(--line); border-radius:12px; }
</style>
""", unsafe_allow_html=True)


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
                value = lines[index + 1]
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


def clear_document():
    st.session_state["document_upload"] = None
    for key in list(st.session_state.keys()):
        if key.startswith("field_"):
            del st.session_state[key]


st.markdown("""
<div class="hero">
  <div class="eyebrow">Private document assistant</div>
  <div class="hero-row"><div class="hero-icon">🔎</div><div><h1>LocalLens</h1>
    <p>Turn documents into editable, reviewable information.</p></div></div>
</div>
<div class="privacy-note">🔒 Designed for local processing &nbsp;·&nbsp; Use synthetic or consented sample documents</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-kicker">Step 1 · Add a document</div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Upload a PDF, scan, or image", type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"], label_visibility="collapsed", key="document_upload")
st.caption("Supported files: PDF, PNG, JPG, TIFF")

if uploaded:
    raw = uploaded.getvalue()
    suffix = Path(uploaded.name).suffix.lower()
    if suffix == ".pdf":
        extracted_text, error = extract_pdf(raw)
    else:
        extracted_text, error = ocr_image(raw)

    if error:
        st.warning(error)

    if extracted_text:
        detected = find_fields(extracted_text)
        doc_id = hashlib.sha1(raw).hexdigest()[:10]
        st.markdown('<div class="status-pill">✓ Document processed</div>', unsafe_allow_html=True)
        st.write("")
        metric_a, metric_b, metric_c, metric_d = st.columns(4)
        metric_a.metric("File type", suffix.lstrip(".").upper())
        metric_b.metric("Fields found", len(detected))
        metric_c.metric("Processing", "On this device")
        metric_d.metric("Next step", "Review values")
        st.markdown('<div class="section-kicker">Step 2 · Review results</div>', unsafe_allow_html=True)
        left, right = st.columns([1.1, 1])
        with left:
            with st.container(border=True):
                st.subheader("Your document")
                st.caption(uploaded.name)
                if suffix != ".pdf" and Image is not None:
                    st.image(raw, use_container_width=True)
                elif suffix == ".pdf":
                    preview = pdf_first_page_preview(raw)
                    if preview:
                        st.image(preview, caption="Page 1 preview", use_container_width=True)
                with st.expander("View extracted text"):
                    st.text_area("Extracted text", extracted_text, height=250, label_visibility="collapsed")
        with right:
            with st.container(border=True):
                st.subheader("Check the details")
                st.caption("Correct anything that doesn’t match the document.")
                if not detected:
                    st.info("No supported fields were detected automatically. You can still review the extracted text.")
                    detected = {"Field 1": ""}
                edited = {}
                for label, value in detected.items():
                    edited[label] = st.text_input(label, value=value, key=f"field_{doc_id}_{label}")
                    status = value_status(label, edited[label])
                    st.caption(f"{status} · confirm against the source")
                with st.expander("Show source text for extracted values"):
                    for label, value in edited.items():
                        st.markdown(f"**{label}**")
                        st.code(source_evidence(extracted_text, value), language=None)
                rows = [{"Field": key, "Value": value} for key, value in edited.items()]
                st.markdown('<div class="section-kicker">Step 3 · Export reviewed details</div>', unsafe_allow_html=True)
                exp1, exp2 = st.columns(2)
                with exp1:
                    st.download_button("Download CSV", csv_bytes(rows), "locallens_results.csv", "text/csv", use_container_width=True, type="primary")
                with exp2:
                    st.download_button("Download JSON", json.dumps(edited, indent=2), "locallens_results.json", "application/json", use_container_width=True)
        privacy_col, clear_col = st.columns([3, 1])
        with privacy_col:
            with st.expander("Privacy and processing details"):
                st.write("This app runs from your computer. PDF reading uses local text extraction, and image reading uses the local Tesseract installation. The prototype does not send documents to a cloud OCR or AI service. Use sample or consented files, and review extracted values.")
        with clear_col:
            st.button("Clear document", on_click=clear_document, use_container_width=True)
        with st.expander("About these results"):
            st.write("Field checks show formatting hints only; they are not accuracy or confidence scores. Extraction uses OCR plus simple text patterns, so check every value against the document before using it.")
    elif not error:
        st.info("No text was found. This may be a scanned PDF; scanned-PDF OCR is a planned next step.")
else:
    st.info("Start with a synthetic sample form containing labels such as Name, Email, Phone, Date of Birth, or ID Number.")
    st.markdown('<div class="section-kicker">A simple three-step workflow</div>', unsafe_allow_html=True)
    feature_cols = st.columns(3)
    for col, icon, title, detail in zip(
        feature_cols,
        ("📄", "✍️", "📤"),
        ("Read locally", "Review together", "Export when ready"),
        ("Extract text from PDFs and images on this computer.", "Check values against source text and edit mistakes.", "Download reviewed fields as CSV or JSON."),
    ):
        with col:
            with st.container(border=True):
                st.markdown(f"### {icon} {title}")
                st.write(detail)
