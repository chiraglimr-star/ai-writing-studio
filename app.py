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
from openai import OpenAI

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Professional ChatGPT Writing Studio & Bypass",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "Professional ChatGPT Writing Studio & Bypass"
DEFAULT_MODEL = "gpt-4o"

MAX_CHUNK_WORDS = 650
MAX_RETRIES = 4
MAX_OUTPUT_TOKENS = 4096
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
    background: linear-gradient(120deg,#10b981,#3b82f6);
    color: white;
    border: none;
}
.stButton button:hover {
    border: 1px solid #6ee7b7;
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

st.title("✍️ Professional ChatGPT Writing Studio & Detector Bypass")
st.caption(
    "Advanced text humanization · Turnitin & GPTZero evasion · "
    "Powered by OpenAI GPT-4o"
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
    "Academic Research (Bypass Focus)": (
        "Use rigorous academic phrasing while maintaining high human perplexity "
        "and variable sentence cadence to slip past Turnitin and GPTZero."
    ),
    "Academic Essay (Student Voice)": (
        "Write in a natural, authentic university student voice. "
        "Avoid over-polished, robotic AI syntax and predictable transitions."
    ),
    "Journalistic": (
        "Prioritize sharp, engaging human rhythm, variable sentence lengths "
        "and natural storytelling flow."
    ),
    "Professional Communication": (
        "Use polished, natural corporate or professional writing "
        "that sounds completely written by an experienced human specialist."
    ),
    "Creative Writing": (
        "Maximize narrative flow, emotional resonance and stylistic unpredictability. "
        "Completely eradicate machine-generated formatting."
    ),
    "Natural English": (
        "Ensure maximum idiomatic fluency and human-like cadence "
        "while strictly maintaining original meaning."
    ),
    "Light Proofreading": (
        "Correct grammar, spelling and punctuation with minimal disruption to the original text."
    )
}

# =========================================================
# SYSTEM INSTRUCTIONS (TURNITIN & GPTZERO BYPASS)
# =========================================================

SYSTEM_PROMPT = """
You are an expert human ghostwriter, advanced academic stylist,
and specialist in evading AI detectors such as Turnitin, GPTZero, 
Copyleaks, and Originality.ai.

Your primary objective is to rewrite and humanize the provided text 
so that it reads as if it was written by an authentic human writer, 
completely eliminating machine-like patterns, predictable structures, 
and statistical uniformity.

CORE PRINCIPLES FOR BYPASSING DETECTORS:

1. BURSTINESS & PERPLEXITY (CRITICAL)
- Avoid uniform, predictable sentence lengths. AI detectors flag texts 
  where every sentence has a similar word count.
- Mix very short, punchy sentences with long, complex, subordinate clauses.
- Vary sentence openings dynamically (never start consecutive sentences 
  with the same grammatical structure or transition words like 'Furthermore', 
  'Moreover', 'In addition', 'Thus').

2. ELIMINATE AI SIGNATURE WORDS & CLICHÉS
- Completely purge typical AI filler words and transition markers: 
  'It is important to note', 'delve', 'testament', 'beacon', 'tapestry', 
  'crucial', 'vital', 'multifaceted', 'in conclusion', 'realm', 'landscape'.
- Use raw, natural, direct human expressions and transitions.

3. MEANING & FACTUAL PRESERVATION
- Preserve the author's original core arguments, reasoning, logic, 
  and factual claims. Do not distort the original intent.
- Maintain names, dates, numbers, citations, and technical terms precisely.

4. IMPERFECTION & NATURAL FLOW
- Introduce natural conversational cadence and organic flow typical 
  of university-level student or professional human writers.

5. OUTPUT
- Return the revised humanized text only. 
- Do not include meta-commentary, explanations, introductions, or conclusions.
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
# OPENAI CLIENT & RETRY HANDLER
# =========================================================

def create_openai_client(api_key: str):
    return OpenAI(api_key=api_key)

def is_retryable_openai_error(error: Exception) -> bool:
    message = str(error).upper()
    indicators = ["429", "500", "502", "503", "504", "RATE_LIMIT", "TIMEOUT"]
    return any(indicator in message for indicator in indicators)

def generate_text_openai(
    client,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    status_callback=None
) -> str:
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if status_callback:
                status_callback(f"OpenAI request: attempt {attempt + 1}")

            started = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            elapsed = time.time() - started
            logger.info("OpenAI request completed in %.2f seconds", elapsed)

            result = response.choices[0].message.content
            if not result or not result.strip():
                raise RuntimeError("OpenAI returned an empty response.")

            return result.strip()

        except Exception as error:
            last_error = error
            if not is_retryable_openai_error(error) or attempt >= MAX_RETRIES:
                raise

            delay = min(2 ** (attempt + 1), 20) + random.uniform(0, 1.5)
            logger.warning("Temporary OpenAI error. Retrying in %.2f seconds: %s", delay, error)
            
            if status_callback:
                status_callback(f"Server busy. Retrying in {delay:.1f}s...")

            time.sleep(delay)

    raise RuntimeError(f"OpenAI request failed: {last_error}")

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
PERSONAL WRITING SAMPLE REFERENCE:
{writing_sample[:4000]}
Analyze the rhythm, sentence breaks, and vocabulary of this sample and replicate its exact human pattern.
"""

    return f"""
EDITING MODE & STRATEGY:
{mode}

STYLE GUIDANCE:
{MODES[mode]}

TARGET LANGUAGE:
{language}

AUTHOR VOICE:
{"Carefully align with the author's personal human writing style." if preserve_voice else "Adopt an organic, highly unpredictable human writing cadence."}

{sample_section}

BYPASS INSTRUCTIONS:
- Smash predictable sentence patterns to beat Turnitin and GPTZero.
- Vary sentence length aggressively (mix short, punchy sentences with long, complex ones).
- Eliminate all robotic AI phrasing, clichés, and generic transition words.
- Keep all factual claims, data points, citations, and terminology fully intact.

TEXT TO EDIT:
{original}

Return the complete humanized text only.
"""

# =========================================================
# DOCUMENT EDITING (PARALLEL SAFE)
# =========================================================

def edit_document_openai(
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
        result = generate_text_openai(client=client, model=model, prompt=prompt)
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
                    f"Humanizing section {completed}/{len(chunks)}"
                )
            except Exception as e:
                logger.error("Chunk processing failed: %s", e)
                raise e

    if any(not item.strip() for item in revised_chunks):
        raise RuntimeError("At least one document section is missing.")

    return "\n\n".join(revised_chunks)

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.header("Studio Settings")

    try:
        saved_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        saved_key = ""

    api_key = st.text_input("OpenAI API Key", value=saved_key, type="password", help="Enter your OpenAI API key starting with sk-...")
    model_name = st.selectbox("OpenAI Model", ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"])

    st.divider()

    editing_mode = st.selectbox("Writing Style & Strategy", list(MODES.keys()))
    target_language = st.selectbox(
        "Target Language",
        ["English", "Azerbaijani", "Turkish", "Russian", "Preserve original language"]
    )

    preserve_voice = st.toggle("Preserve author's writing voice", value=True)
    writing_sample = st.text_area("Personal Writing Sample", height=120)
    st.caption("The sample is used to mimic your personal human writing style.")

# =========================================================
# INPUT
# =========================================================

left, right = st.columns(2)

with left:
    st.subheader("📥 Original Document")
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
    st.subheader("📤 Humanized & Refined Document")
    st.text_area("Final result", value=st.session_state.result, height=480, key="result_preview")

# =========================================================
# PROCESSING
# =========================================================

st.divider()

if st.button("🚀 START HUMANIZATION & BYPASS REFINEMENT", use_container_width=True):
    if not api_key.strip():
        st.error("Enter your OpenAI API key.")
    elif not input_text.strip():
        st.warning("Please provide a document.")
    else:
        progress = st.progress(0)
        status = st.empty()
        start_time = time.time()

        try:
            client = create_openai_client(api_key)
            chunks = split_document(input_text)
            st.info(f"Document: {stats['Words']} words · {len(chunks)} sections")

            def update_progress(current, total, message):
                progress.progress(min(current / total, 1.0))
                status.info(message)

            revised = edit_document_openai(
                client=client,
                model=model_name,
                original=input_text,
                mode=editing_mode,
                language=target_language,
                preserve_voice=preserve_voice,
                writing_sample=writing_sample,
                progress_callback=update_progress
            )

            elapsed = time.time() - start_time
            st.session_state.result = revised
            st.session_state.original = input_text
            st.session_state.processing_time = elapsed

            st.session_state.history.append({
                "words": stats["Words"],
                "time": round(elapsed, 2),
                "mode": editing_mode
            })

            progress.progress(1.0)
            status.success(f"Humanization and bypass completed in {elapsed:.1f} seconds.")
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
    c2.metric("Humanized Words", after["Words"])
    c3.metric("Paragraphs", after["Paragraphs"])
    c4.metric("Processing Time", f"{st.session_state.processing_time:.1f}s")

    tab1, tab2, tab3 = st.tabs(["Final Document", "Comparison", "Export"])

    with tab1:
        st.text_area("Editable final text", value=result, height=450)

    with tab2:
        diff = difflib.unified_diff(
            st.session_state.original.splitlines(),
            result.splitlines(),
            fromfile="Original",
            tofile="Humanized",
            lineterm=""
        )
        st.code("\n".join(diff), language="diff")

    with tab3:
        st.download_button("Download TXT", data=result.encode("utf-8"), file_name="humanized_document.txt", mime="text/plain")
        st.download_button("Download Markdown", data=result.encode("utf-8"), file_name="humanized_document.md", mime="text/markdown")

        try:
            from docx import Document
            doc = Document()
            for paragraph in result.split("\n"):
                doc.add_paragraph(paragraph)
            buffer = io.BytesIO()
            doc.save(buffer)
            st.download_button("Download DOCX", data=buffer.getvalue(), file_name="humanized_document.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
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
st.caption("Professional ChatGPT Writing Studio & Bypass · Powered by OpenAI GPT-4o")
