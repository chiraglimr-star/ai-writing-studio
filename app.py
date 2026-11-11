from __future__ import annotations

import io
import re
import time
import random
import logging
import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import streamlit as st
from google import genai
from google.genai import types

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Professional AI Writing Studio",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "Professional AI Writing Studio"

# Google AI Studio model təyinatı
DEFAULT_MODEL = "gemini-3.8-flash"

MAX_CHUNK_WORDS = 650
MAX_RETRIES = 4
REQUEST_TIMEOUT_MS = 120_000
MAX_OUTPUT_TOKENS = 8192
MAX_PARALLEL_REQUESTS = 2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("writing_studio")

# =========================================================
# UI & STYLING
# =========================================================

st.markdown("""
<style>
.stApp {
    background: #080b12;
    color: #e5e7eb;
}
.block-container {
    max-width: 1550px;
    padding-top: 2rem;
}
section[data-testid="stSidebar"] {
    background: #101522;
}
.stTextArea textarea {
    background: #111827 !important;
    color: #f9fafb !important;
    border: 1px solid #374151 !important;
    border-radius: 10px !important;
    font-size: 15px !important;
}
.stButton button, .stDownloadButton button {
    width: 100%;
    min-height: 44px;
    border-radius: 10px;
    font-weight: 650;
    background: linear-gradient(120deg,#6366f1,#a855f7);
    color: white;
    border: none;
}
.stButton button:hover {
    border: 1px solid #a78bfa;
    color: white;
}
div[data-testid="stMetric"] {
    background: #111827;
    padding: 14px;
    border-radius: 12px;
    border: 1px solid #293449;
}
</style>
""", unsafe_allow_html=True)

st.title("✍️ Professional AI Writing Studio")
st.caption(
    "Academic editing · Natural language refinement · "
    "Document quality assurance"
)

# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "result": "",
    "original": "",
    "processing_time": 0.0,
    "history": [],
    "audit_report": "",
    "last_error": ""
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# WRITING MODES
# =========================================================

MODES = {
    "Academic Research": (
        "Use precise scholarly language, preserve the research "
        "argument, distinguish evidence from interpretation, "
        "and maintain appropriate academic terminology."
    ),
    "Academic Essay": (
        "Use clear university-level writing. Preserve the student's "
        "own reasoning and avoid unnecessary complexity."
    ),
    "Journalistic": (
        "Use concise, clear, engaging journalistic language."
    ),
    "Professional Communication": (
        "Use polished, professional and direct language."
    ),
    "Creative Writing": (
        "Improve narrative flow, imagery and emotional clarity "
        "without changing the author's intended meaning."
    ),
    "Natural English": (
        "Improve idiomatic fluency and natural expression."
    ),
    "Light Proofreading": (
        "Correct grammar, spelling and punctuation with minimal changes."
    )
}

SYSTEM_PROMPT = """
You are a professional editor and writing-quality specialist.

Your task is to improve the supplied document while preserving
the author's intended meaning and intellectual contribution.

RULES:

1. Preserve the original argument, thesis and reasoning.
2. Never invent facts, statistics, sources or quotations.
3. Preserve names, dates, numbers and technical terminology.
4. Preserve citations and references exactly unless correction
   is explicitly requested.
5. Do not remove important qualifications or limitations.
6. Maintain the requested language.
7. Use clear and natural language appropriate to the genre.
8. Do not add unsupported claims.
9. Do not fabricate personal experiences or opinions.
10. Return only the edited document.
"""

# =========================================================
# TEXT UTILITIES
# =========================================================

def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, re.UNICODE))

def count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?]+", text))

def count_paragraphs(text: str) -> int:
    return len([p for p in text.split("\n") if p.strip()])

def get_stats(text: str) -> dict:
    return {
        "Words": count_words(text),
        "Sentences": count_sentences(text),
        "Paragraphs": count_paragraphs(text),
        "Characters": len(text)
    }

# =========================================================
# FILE IMPORT
# =========================================================

def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()

    if filename.endswith((".txt", ".md")):
        return uploaded_file.getvalue().decode(
            "utf-8",
            errors="replace"
        )

    if filename.endswith(".docx"):
        try:
            from docx import Document
            document = Document(
                io.BytesIO(uploaded_file.getvalue())
            )
            content = []
            for paragraph in document.paragraphs:
                if paragraph.text.strip():
                    content.append(paragraph.text)
            for table in document.tables:
                for row in table.rows:
                    content.append(
                        " | ".join(cell.text for cell in row.cells)
                    )
            return "\n\n".join(content)
        except ImportError:
            raise ValueError("DOCX support requires python-docx.")

    raise ValueError("Unsupported file format.")

# =========================================================
# DOCUMENT CHUNKING
# =========================================================

def split_long_paragraph(paragraph: str, max_words: int) -> list[str]:
    words = paragraph.split()
    if len(words) <= max_words:
        return [paragraph]
    chunks = []
    for start in range(0, len(words), max_words):
        chunks.append(" ".join(words[start:start + max_words]))
    return chunks

def split_document(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]
    chunks = []
    current = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = count_words(paragraph)
        if paragraph_words > max_words:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_words = 0
            chunks.extend(split_long_paragraph(paragraph, max_words))
            continue

        if current_words + paragraph_words > max_words:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_words = paragraph_words
        else:
            current.append(paragraph)
            current_words += paragraph_words

    if current:
        chunks.append("\n\n".join(current))

    return chunks

# =========================================================
# GEMINI CLIENT & TIMEOUT
# =========================================================

def create_client(api_key: str):
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS
        )
    )

# =========================================================
# RETRY LOGIC (503 & Rate Limit Handler)
# =========================================================

def is_retryable_error(error: Exception) -> bool:
    message = str(error).upper()
    indicators = [
        "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
        "500", "502", "504", "408", "TIMEOUT"
    ]
    return any(indicator in message for indicator in indicators)

def generate_text(
    client,
    model: str,
    prompt: str,
    temperature: float = 0.4,
    status_callback=None
) -> str:
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if status_callback:
                status_callback(f"API request: attempt {attempt + 1}")

            started = time.time()
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=temperature,
                    max_output_tokens=MAX_OUTPUT_TOKENS
                )
            )
            elapsed = time.time() - started
            logger.info("Gemini request completed in %.2f seconds", elapsed)

            result = response.text
            if not result or not result.strip():
                raise RuntimeError("Gemini returned an empty response.")

            return result.strip()

        except Exception as error:
            last_error = error
            if not is_retryable_error(error) or attempt >= MAX_RETRIES:
                raise

            delay = min(2 ** (attempt + 1), 20) + random.uniform(0, 1.5)
            logger.warning("Temporary API error. Retrying in %.2f seconds: %s", delay, error)
            
            if status_callback:
                status_callback(f"Server busy. Retrying in {delay:.1f}s...")

            time.sleep(delay)

    raise RuntimeError(f"Gemini request failed: {last_error}")

# =========================================================
# PROMPT BUILDER
# =========================================================

def build_edit_prompt(
    original: str,
    mode: str,
    language: str,
    preserve_voice: bool,
    writing_sample: str
) -> str:
    sample_section = ""
    if writing_sample.strip():
        sample_section = f"""
AUTHOR'S WRITING SAMPLE:
{writing_sample[:4000]}
Use this only as a reference for vocabulary and tone.
"""

    return f"""
DOCUMENT TYPE:
{mode}

EDITING REQUIREMENTS:
{MODES[mode]}

TARGET LANGUAGE:
{language}

AUTHOR VOICE:
{"Preserve the author's existing writing style." if preserve_voice else "Use a clear professional style."}

{sample_section}

DOCUMENT TO EDIT:
{original}

Return the complete edited document.
"""

# =========================================================
# DOCUMENT EDITING (PARALLEL SAFE)
# =========================================================

def edit_document(
    client,
    model,
    original,
    mode,
    language,
    preserve_voice,
    writing_sample,
    progress_callback
):
    chunks = split_document(original)
    if not chunks:
        raise ValueError("The document is empty.")

    revised_chunks = [""] * len(chunks)

    def process_chunk(index, chunk):
        prompt = build_edit_prompt(
            original=chunk,
            mode=mode,
            language=language,
            preserve_voice=preserve_voice,
            writing_sample=writing_sample
        )
        result = generate_text(client=client, model=model, prompt=prompt)
        return index, result

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        futures = {
            executor.submit(process_chunk, i, chunk): i
            for i, chunk in enumerate(chunks)
        }

        completed = 0
        for future in as_completed(futures):
            try:
                index, result = future.result()
                revised_chunks[index] = result
                completed += 1
                progress_callback(
                    completed,
                    len(chunks),
                    f"Completed section {completed}/{len(chunks)}"
                )
            except Exception as e:
                logger.error("Chunk processing failed: %s", e)
                raise e

    if any(not item.strip() for item in revised_chunks):
        raise RuntimeError("At least one document section is missing.")

    return "\n\n".join(revised_chunks)

# =========================================================
# QUALITY REVIEW
# =========================================================

def review_document(
    client,
    model,
    original,
    revised,
    status_callback=None
):
    review_prompt = f"""
Compare the original and edited documents. Check if main arguments, names, dates, numbers, and citations are fully preserved.
Return a concise list of issues or state if everything is correct.

ORIGINAL:
{original[:25000]}

EDITED:
{revised[:25000]}
"""
    return generate_text(
        client, model, review_prompt,
        temperature=0.1, status_callback=status_callback
    )

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.header("Studio Settings")

    try:
        saved_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        saved_key = ""

    api_key = st.text_input("Gemini API Key", value=saved_key, type="password")
    model_name = st.text_input("Gemini Model", value=DEFAULT_MODEL)

    st.divider()

    editing_mode = st.selectbox("Editing Mode", list(MODES.keys()))
    target_language = st.selectbox(
        "Target Language",
        ["English", "Azerbaijani", "Turkish", "Russian", "Preserve original language"]
    )

    preserve_voice = st.toggle("Preserve author's voice", value=True)
    run_audit = st.toggle("Run consistency review", value=False)

    writing_sample = st.text_area("Writing Sample", height=120)
    st.caption("Use your previous writing as a style reference.")

# =========================================================
# INPUT
# =========================================================

left, right = st.columns(2)

with left:
    st.subheader("Original Document")
    uploaded_file = st.file_uploader("Upload TXT, MD or DOCX", type=["txt", "md", "docx"])
    uploaded_text = ""

    if uploaded_file:
        try:
            uploaded_text = read_uploaded_file(uploaded_file)
        except Exception as error:
            st.error(str(error))

    input_text = st.text_area("Document text", value=uploaded_text, height=480, key="document_input")
    stats = get_stats(input_text)
    st.caption(f"{stats['Words']} words · {stats['Sentences']} sentences · {stats['Paragraphs']} paragraphs")

with right:
    st.subheader("Edited Document")
    st.text_area("Final result", value=st.session_state.result, height=480, key="result_preview")

# =========================================================
# PROCESSING
# =========================================================

st.divider()

if st.button("START DOCUMENT EDITING", use_container_width=True):
    if not api_key.strip():
        st.error("Enter your Gemini API key.")
    elif not input_text.strip():
        st.warning("Please provide a document.")
    else:
        progress = st.progress(0)
        status = st.empty()
        start_time = time.time()

        try:
            client = create_client(api_key)
            chunks = split_document(input_text)
            st.info(f"Document: {stats['Words']} words · {len(chunks)} sections")

            def update_progress(current, total, message):
                progress.progress(min(current / total, 1.0))
                status.info(message)

            revised = edit_document(
                client=client,
                model=model_name,
                original=input_text,
                mode=editing_mode,
                language=target_language,
                preserve_voice=preserve_voice,
                writing_sample=writing_sample,
                progress_callback=update_progress
            )

            audit_report = ""
            if run_audit:
                status.info("Checking factual consistency...")
                audit_report = review_document(client, model_name, input_text, revised)

            elapsed = time.time() - start_time
            st.session_state.result = revised
            st.session_state.original = input_text
            st.session_state.processing_time = elapsed
            st.session_state.audit_report = audit_report

            st.session_state.history.append({
                "words": stats["Words"],
                "time": round(elapsed, 2),
                "mode": editing_mode
            })

            progress.progress(1.0)
            status.success(f"Editing completed in {elapsed:.1f} seconds.")
            st.rerun()

        except Exception as error:
            logger.exception("Processing failed")
            status.empty()
            progress.empty()
            st.error(f"Processing failed: {error}")

# =========================================================
# RESULTS
# =========================================================

if st.session_state.result:
    result = st.session_state.result
    st.divider()
    st.header("Document Analysis")

    before = get_stats(st.session_state.original)
    after = get_stats(result)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Original Words", before["Words"])
    c2.metric("Edited Words", after["Words"])
    c3.metric("Paragraphs", after["Paragraphs"])
    c4.metric("Processing Time", f"{st.session_state.processing_time:.1f}s")

    tab1, tab2, tab3, tab4 = st.tabs(["Final Document", "Comparison", "Quality Review", "Export"])

    with tab1:
        st.text_area("Editable final text", value=result, height=450)

    with tab2:
        diff = difflib.unified_diff(
            st.session_state.original.splitlines(),
            result.splitlines(),
            fromfile="Original",
            tofile="Edited",
            lineterm=""
        )
        st.code("\n".join(diff), language="diff")

    with tab3:
        if st.session_state.audit_report:
            st.write(st.session_state.audit_report)
        else:
            st.info("Consistency review was not enabled.")

    with tab4:
        st.download_button("Download TXT", data=result.encode("utf-8"), file_name="edited_document.txt", mime="text/plain")
        st.download_button("Download Markdown", data=result.encode("utf-8"), file_name="edited_document.md", mime="text/markdown")

        try:
            from docx import Document
            doc = Document()
            for paragraph in result.split("\n"):
                doc.add_paragraph(paragraph)
            buffer = io.BytesIO()
            doc.save(buffer)
            st.download_button("Download DOCX", data=buffer.getvalue(), file_name="edited_document.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except ImportError:
            st.info("Install python-docx for DOCX export.")

# =========================================================
# HISTORY
# =========================================================

if st.session_state.history:
    with st.expander("Processing History"):
        for item in reversed(st.session_state.history[-10:]):
            st.write(f"{item['words']} words · {item['time']} seconds · {item['mode']}")

st.divider()
st.caption("Professional AI Writing Studio · Powered by Google Gemini")
