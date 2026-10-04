import hashlib
from html import escape
import json
from pathlib import Path

import streamlit as st
from locallens_core import (
    csv_bytes,
    extract_pdf,
    find_fields,
    draw_prepared_pdf_page,
    draw_prepared_preview,
    ocr_image,
    pdf_page_count,
    prepare_image_preview,
    prepare_pdf_page_preview,
    pytesseract,
    redact_image_copy,
    redact_pdf_copy,
    source_evidence,
    value_status,
)


st.set_page_config(page_title="LocalLens", page_icon="🔎", layout="wide")
st.markdown("""
<style>
  :root { --ink:#3e342f; --muted:#88786f; --panel:#fffdf9; --panel2:#f4ece3; --line:#e5d8ca; --gold:#b87860; --mint:#628b70; }
  html, body, [data-testid="stAppViewContainer"] { background-color:#f7f3ed !important; }
  .stApp, [data-testid="stAppViewContainer"] { background:radial-gradient(ellipse at 50% -20%, #eee0d2 0%, #f7f3ed 58%) fixed !important; color:var(--ink); }
  [data-testid="stMain"] { background:transparent !important; }
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
  .status-pill.review-pill { color:#8a542c; background:#fff0dc; border-color:#edcfaa; }
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
  .dashboard-card { min-height:128px; box-sizing:border-box; padding:1rem 1.05rem; border:1px solid #e1d0c1; border-radius:17px; background:#fffaf5; box-shadow:0 5px 16px rgba(92,65,49,.06); }
  .dashboard-card.type { background:#f2e3d5; }
  .dashboard-card.fields { background:#e9eee4; border-color:#d5dfcf; }
  .dashboard-card.process { background:#efe3df; border-color:#e1cbc3; }
  .dashboard-card.next { background:#eee8dc; border-color:#e0d6c5; }
  .dashboard-card-head { display:flex; align-items:center; gap:.55rem; color:#78665b; font-size:.78rem; font-weight:700; }
  .dashboard-card-icon { display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:10px; background:rgba(255,255,255,.65); font-size:1rem; }
  .dashboard-card-value { margin-top:.72rem; color:#3e342f; font-size:1.28rem; font-weight:750; line-height:1.2; }
  .dashboard-card-detail { margin-top:.28rem; color:#88786f; font-size:.76rem; }
  .step-chip { padding:.75rem 1rem; border:1px solid #e5d8ca; border-radius:13px; background:#fffaf5; color:#88786f; font-size:.9rem; font-weight:650; }
  .step-chip.active { background:#b87860; border-color:#b87860; color:#fffaf5; }
  .step-chip.done { background:#e8efe5; border-color:#d2dfcc; color:#4f7054; }
  .screen-title { margin:.25rem 0 .3rem; }
  .screen-intro { color:#76675e; margin-bottom:1rem; }
  .welcome-card { min-height:205px; padding:1.15rem 1.2rem; border:1px solid #e1d0c1; border-radius:19px; box-shadow:0 7px 18px rgba(92,65,49,.06); transition:transform .18s ease, box-shadow .18s ease; }
  .welcome-card:hover { transform:translateY(-3px); box-shadow:0 11px 24px rgba(92,65,49,.11); }
  .welcome-card.read { background:linear-gradient(145deg,#f4e4d7,#fbf5ee); }
  .welcome-card.review { background:linear-gradient(145deg,#e8eee3,#f6f8f2); border-color:#d4dfcd; }
  .welcome-card.export { background:linear-gradient(145deg,#efe2de,#faf3f0); border-color:#e3cfca; }
  .welcome-step { color:#9a6d5a; font-size:.7rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
  .welcome-icon { display:flex; align-items:center; justify-content:center; width:48px; height:48px; margin:.8rem 0 .65rem; border-radius:15px; background:rgba(255,255,255,.72); font-size:1.45rem; }
  .welcome-card h3 { margin:.1rem 0 .35rem; font-size:1.08rem; }
  .welcome-card p { margin:0; color:#74665e; font-size:.88rem; line-height:1.5; }
  hr { border-color:var(--line); }
  .stMarkdown, .stCaption, label, label p, [data-testid="stWidgetLabel"] p, [data-testid="stFileUploader"] { color:var(--ink) !important; }
  [data-testid="stCode"], [data-testid="stCode"] pre, [data-testid="stCode"] code,
  [data-testid="stCode"] pre span { background:#f5ece3 !important; color:#493a33 !important; border-color:#e5d8ca !important; }
  [data-testid="stExpander"] { background:#fffdf9; border:1px solid var(--line); border-radius:12px; }
  [data-testid="stExpander"] details, [data-testid="stExpander"] summary,
  [data-testid="stExpander"] summary * { background:#fffaf5 !important; color:#493a33 !important; }
</style>
""", unsafe_allow_html=True)


def clear_document():
    st.session_state["document_upload"] = None
    for key in list(st.session_state.keys()):
        if key.startswith(("field_", "pdf_pages_")):
            del st.session_state[key]


st.markdown("""
<div class="hero">
  <div class="eyebrow">Private document assistant</div>
  <div class="hero-row"><div class="hero-icon">🔎</div><div><h1>LocalLens</h1>
    <p>Turn documents into editable, reviewable information.</p></div></div>
</div>
<div class="privacy-note">🔒 Files are processed by the machine running this app. When you run it on your own PC, processing stays on your PC. Files remain in the active app session until you clear them or the session ends.</div>
""", unsafe_allow_html=True)

def reset_workflow():
    for key in list(st.session_state.keys()):
        if key == "document_upload" or key.startswith(("field_", "locallens_", "pdf_pages_")):
            del st.session_state[key]
    st.session_state["workflow_step"] = 1


st.session_state.setdefault("workflow_step", 1)
step = st.session_state["workflow_step"]
step_cols = st.columns(3)
for index, (col, label) in enumerate(zip(step_cols, ("1 · Upload", "2 · Review", "3 · Export")), start=1):
    cls = "active" if index == step else ("done" if index < step else "")
    with col:
        st.markdown(f'<div class="step-chip {cls}">{label}</div>', unsafe_allow_html=True)
st.write("")

if step == 1:
    st.markdown('<h2 class="screen-title">Add your document</h2><div class="screen-intro">Choose a PDF or image to extract a few useful details locally.</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload a PDF, scan, or image", type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"], label_visibility="collapsed", key="document_upload")
    st.caption("Supported files: PDF, PNG, JPG, TIFF")
    if uploaded:
        raw = uploaded.getvalue()
        suffix = Path(uploaded.name).suffix.lower()
        extracted_text, error = "", ""
        selected_pages = []
        pdf_ready = True
        pdf_has_results = False
        if suffix == ".pdf":
            try:
                page_count = pdf_page_count(raw)
            except Exception as exc:
                page_count, pdf_ready = 0, False
                error = f"LocalLens couldn’t open this PDF ({exc}). Check that it is a valid PDF, then try again."
            if pdf_ready:
                st.markdown("### Choose PDF pages")
                st.caption(f"This PDF has {page_count} page{'s' if page_count != 1 else ''}. Select one or more pages for LocalLens to read. All pages are selected by default.")
                selected_pages = st.multiselect(
                    "Pages to read",
                    options=list(range(1, page_count + 1)),
                    default=list(range(1, page_count + 1)),
                    format_func=lambda page_number: f"Page {page_number}",
                    key=f"pdf_pages_{hashlib.sha1(raw).hexdigest()[:10]}",
                    help="Choose only the pages you want to extract and review.",
                )
                read_key = hashlib.sha1(raw + (",".join(map(str, selected_pages))).encode("ascii")).hexdigest()
                if selected_pages and st.button("Read selected page(s) →", type="primary", use_container_width=True):
                    try:
                        extracted_text, error = extract_pdf(raw, selected_pages)
                    except Exception as exc:
                        extracted_text, error = "", f"LocalLens couldn’t read the selected PDF pages ({exc}). Check the file and try again."
                    st.session_state["locallens_read_key"] = read_key
                    st.session_state["locallens_read_text"] = extracted_text
                    st.session_state["locallens_read_error"] = error
                    st.session_state["locallens_selected_pages"] = selected_pages
                elif not selected_pages:
                    st.warning("Select at least one page to continue.")
                if st.session_state.get("locallens_read_key") == read_key:
                    pdf_has_results = True
                    extracted_text = st.session_state.get("locallens_read_text", "")
                    error = st.session_state.get("locallens_read_error", "")
            elif error:
                pass
        else:
            try:
                extracted_text, error = ocr_image(raw)
            except Exception as exc:
                extracted_text, error = "", f"LocalLens couldn’t open this file ({exc}). Check that it is a valid PDF or image, then try another file."
        if error:
            st.warning(error)
            st.caption("Your original file is not changed. Try a clear PDF, PNG, JPG, or TIFF file.")
            if st.button("Start over", on_click=reset_workflow):
                st.rerun()
        elif not extracted_text:
            if suffix == ".pdf" and not pdf_has_results:
                st.info("Choose the PDF pages you want, then select “Read selected page(s)” to continue.")
            else:
                st.warning("No readable text was found. Check the scan quality and make sure local Tesseract OCR is installed for images or scanned PDFs.")
                st.caption("Try a sharper, well-lit image or a text-based PDF. Your original file is not changed.")
                if st.button("Start over", on_click=reset_workflow):
                    st.rerun()
        else:
            doc_id = hashlib.sha1(raw).hexdigest()[:10]
            detected = find_fields(extracted_text)
            st.session_state["locallens_document"] = raw
            st.session_state["locallens_name"] = uploaded.name
            st.session_state["locallens_suffix"] = suffix
            st.session_state["locallens_text"] = extracted_text
            st.session_state["locallens_fields"] = detected
            st.session_state["locallens_doc_id"] = doc_id
            if suffix != ".pdf":
                st.session_state["locallens_selected_pages"] = []
            summary_cards = st.columns(3)
            page_summary = f"Pages {', '.join(map(str, selected_pages))}" if suffix == ".pdf" else "Single image"
            for col, (label, value) in zip(summary_cards, (("File type", suffix.lstrip(".").upper()), ("Fields found", str(len(detected))), ("Pages read", page_summary))):
                with col:
                    st.metric(label, value)
            if not detected:
                st.info("Text was read, but no supported fields were detected. You can still inspect the text in the review step.")
            if st.button("Continue to review →", type="primary", use_container_width=True):
                st.session_state["workflow_step"] = 2
                st.rerun()
    else:
        st.info("Try the fictional sample form or another synthetic/consented document.")
        st.markdown('<div class="section-kicker">A simple, privacy-first workflow</div>', unsafe_allow_html=True)
        feature_cols = st.columns(3)
        cards = [
            ("read", "01 · PROCESS", "🛡️", "Read on this device", "PDF text and image OCR are handled by local tools in your app session."),
            ("review", "02 · CHECK", "🔎", "Review with context", "Compare extracted details with the source and correct anything that looks wrong."),
            ("export", "03 · USE", "📤", "Export when ready", "Download the reviewed fields as CSV or JSON for your next step."),
        ]
        for col, (style, number, icon, title, detail) in zip(feature_cols, cards):
            with col:
                st.markdown(
                    f'<div class="welcome-card {style}"><div class="welcome-step">{escape(number)}</div><div class="welcome-icon">{icon}</div><h3>{escape(title)}</h3><p>{escape(detail)}</p></div>',
                    unsafe_allow_html=True,
                )

elif step == 2:
    raw = st.session_state.get("locallens_document")
    if raw is None:
        st.session_state["workflow_step"] = 1
        st.rerun()
    name = st.session_state["locallens_name"]
    suffix = st.session_state["locallens_suffix"]
    extracted_text = st.session_state["locallens_text"]
    detected = st.session_state.get("locallens_fields", {}) or {"Field 1": ""}
    doc_id = st.session_state["locallens_doc_id"]
    st.markdown('<h2 class="screen-title">Review extracted details</h2><div class="screen-intro">Compare each value with the source, check any flagged fields, and correct anything that looks wrong.</div>', unsafe_allow_html=True)
    left, right = st.columns([1.05, 1])
    edited = {label: st.session_state.get(f"field_{doc_id}_{label}", value) for label, value in detected.items()}
    with right:
        with st.container(border=True):
            st.subheader("Check the fields")
            st.caption("These are suggestions. Correct anything that doesn’t match.")
            st.info("Evidence labels show whether a value appears in the extracted source text and passes a basic format check. They are not AI or OCR accuracy scores.")
            edited = {}
            for label, value in detected.items():
                edited[label] = st.text_input(label, value=value, key=f"field_{doc_id}_{label}")
                value = edited[label]
                evidence = source_evidence(extracted_text, value)
                source_found = bool(value.strip()) and not evidence.startswith("Source text wasn’t matched")
                format_ok = value_status(label, value) == "Format looks OK" or (label == "Name" and bool(value.strip()))
                if source_found and format_ok:
                    st.markdown('<span class="status-pill">✓ Found in source · format looks valid</span>', unsafe_allow_html=True)
                else:
                    reasons = []
                    if not source_found:
                        reasons.append("not matched in source")
                    if not format_ok:
                        reasons.append(value_status(label, value).lower())
                    st.markdown('<span class="status-pill review-pill">⚠ Please review · ' + escape(" · ".join(reasons)) + '</span>', unsafe_allow_html=True)
                st.caption("Check this value against the document before exporting.")
            common_fields = {"Name", "Email", "Phone", "Date", "ID Number"}
            missing_fields = sorted(common_fields - set(detected))
            if missing_fields:
                st.warning("Not found in this document: " + ", ".join(missing_fields) + ". You can still review and export the fields that were found.")
            with st.expander("Show source text for these values"):
                for label, value in edited.items():
                    st.markdown(f"**{label}**")
                    st.code(source_evidence(extracted_text, value), language=None)
            with st.expander("Optional · redact fields in a copy"):
                st.caption("Select details to cover with permanent black bars in a separate download.")
                redact_values = {}
                for label, value in edited.items():
                    if value and st.checkbox(f"Redact {label}", key=f"redact_{doc_id}_{label}"):
                        redact_values[label] = value
    with left:
        with st.container(border=True):
            st.subheader("Document preview")
            st.caption(name)
            st.caption("Matched values are highlighted where LocalLens can locate them. Use the source text and the original document to confirm each value.")
            preview_cache = st.session_state.setdefault("locallens_preview_cache", {})
            if suffix == ".pdf":
                pages_to_preview = st.session_state.get("locallens_selected_pages", [])
                prepared_pages = []
                for page_number in pages_to_preview:
                    cache_key = f"{doc_id}:pdf:{page_number}"
                    if cache_key not in preview_cache:
                        preview_cache[cache_key] = prepare_pdf_page_preview(raw, page_number)
                    prepared_pages.append(preview_cache[cache_key])
                previews = [draw_prepared_pdf_page(item, edited) for item in prepared_pages if item]
                highlighted = sorted({label for _, _, page_labels in previews for label in page_labels})
                preview = bool(previews)
                for page_number, page_image, page_labels in previews:
                    st.image(page_image, caption=f"PDF page {page_number}" + (" · matched values highlighted" if page_labels else ""), use_container_width=True)
                if not highlighted:
                    st.caption("Text in digital PDFs is highlighted when matched. For scanned pages, compare the preview with the extracted values.")
            else:
                cache_key = f"{doc_id}:image"
                if cache_key not in preview_cache:
                    preview_cache[cache_key] = prepare_image_preview(raw)
                preview, highlighted = draw_prepared_preview(preview_cache[cache_key], edited)
            if suffix != ".pdf" and preview:
                st.image(preview, caption="Detected values highlighted" if highlighted else "Document preview", use_container_width=True)
                if highlighted:
                    st.caption("Highlighted fields: " + ", ".join(highlighted))
                elif pytesseract is None:
                    st.caption("Local OCR is needed to mark source locations in the preview.")
                else:
                    st.caption("Could not match these values to visible words. Check them in the source text.")
            elif suffix != ".pdf" and not preview:
                st.image(raw, use_container_width=True)
            with st.expander("View extracted text"):
                st.text_area("Extracted text", extracted_text, height=240, label_visibility="collapsed")
    nav_back, nav_spacer, nav_next = st.columns([1, 2, 1])
    with nav_back:
        if st.button("← Change document", use_container_width=True):
            st.session_state["workflow_step"] = 1
            st.rerun()
    with nav_next:
        if st.button("Continue to export →", type="primary", use_container_width=True):
            st.session_state["locallens_reviewed"] = edited
            st.session_state["locallens_redact_values"] = redact_values
            st.session_state["workflow_step"] = 3
            st.rerun()
    if st.button("Start over with another document", key="review_start_over"):
        reset_workflow()
        st.rerun()

elif step == 3:
    if "locallens_document" not in st.session_state:
        st.session_state["workflow_step"] = 1
        st.rerun()
    edited = st.session_state.get("locallens_reviewed", {})
    st.markdown('<h2 class="screen-title">Your reviewed data is ready</h2><div class="screen-intro">Download a copy in the format that fits your next step.</div>', unsafe_allow_html=True)
    st.success(f"{len(edited)} fields ready to export")
    with st.container(border=True):
        st.subheader("Export preview")
        st.dataframe([{"Field": key, "Reviewed value": value} for key, value in edited.items()], hide_index=True, use_container_width=True)
        rows = [{"Field": key, "Value": value} for key, value in edited.items()]
        export_csv, export_json = st.columns(2)
        with export_csv:
            st.download_button("Download CSV", csv_bytes(rows), "locallens_results.csv", "text/csv", use_container_width=True, type="primary")
        with export_json:
            st.download_button("Download JSON", json.dumps(edited, indent=2), "locallens_results.json", "application/json", use_container_width=True)
    redact_values = st.session_state.get("locallens_redact_values", {})
    if redact_values:
        with st.container(border=True):
            st.subheader("Privacy copy")
            st.caption("Create a separate flattened copy with the selected values permanently covered. This runs only when you click the button.")
            redaction_key = hashlib.sha1(
                st.session_state["locallens_document"] + json.dumps(redact_values, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if st.button("Create redacted copy", key="create_redacted_copy"):
                with st.spinner("Applying redactions locally…"):
                    if st.session_state["locallens_suffix"] == ".pdf":
                        result = redact_pdf_copy(st.session_state["locallens_document"], redact_values)
                    else:
                        result = redact_image_copy(st.session_state["locallens_document"], redact_values)
                st.session_state["locallens_redaction_result"] = (redaction_key, result)
            saved_result = st.session_state.get("locallens_redaction_result")
            if saved_result and saved_result[0] == redaction_key:
                redacted_copy, redacted_labels, missing_labels = saved_result[1]
                if st.session_state["locallens_suffix"] == ".pdf":
                    redacted_name, mime = "locallens_redacted.pdf", "application/pdf"
                else:
                    redacted_name, mime = "locallens_redacted.png", "image/png"
                if redacted_copy:
                    st.success("Redacted: " + ", ".join(redacted_labels))
                    st.download_button("Download redacted copy", redacted_copy, redacted_name, mime, use_container_width=True, type="primary")
                    st.caption("This copy is flattened. Check it visually before sharing; the original file is unchanged.")
                else:
                    st.warning("Could not safely locate every selected field in the document: " + ", ".join(missing_labels) + ". No redacted copy was created.")
    st.caption("The extracted values are only as reliable as the source text. Keep reviewing sensitive details before use.")
    prev_col, clear_col = st.columns([1, 1])
    with prev_col:
        if st.button("← Back to review", use_container_width=True):
            st.session_state["workflow_step"] = 2
            st.rerun()
    with clear_col:
        st.button("Finish and clear document", on_click=reset_workflow, use_container_width=True)
    if st.button("Start over with another document", key="export_start_over"):
        reset_workflow()
        st.rerun()
