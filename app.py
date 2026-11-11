from __future__ import annotations

import io
import re
import time
import difflib
import logging
from typing import List, Optional

import streamlit as st
from google import genai
from google.genai import types

# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Professional AI Writing Studio & Bypass",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "Professional AI Writing Studio & Bypass"
DEFAULT_MODEL = "gemini-3.8-flash"

MAX_CHUNK_WORDS = 900
MAX_RETRIES = 3
REQUEST_TIMEOUT_MS = 120_000
MAX_OUTPUT_TOKENS = 8192

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("writing_studio")

# =========================================================
# DESIGN
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

st.title("✍️ Professional AI Writing Studio & Detector Bypass")
st.caption(
    "Advanced text humanization · Turnitin & GPTZero evasion · "
    "Style consistency · Document quality assurance"
)

# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "result": "",
    "original": "",
    "processing_time": 0.0,
    "last_error": "",
    "audit_report": "",
    "history": []
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# =========================================================
# WRITING MODES (BYPASS & HUMANIZATION FOCUS)
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
        "Correct grammar, spelling, punctuation and obvious awkwardness "
        "with minimal disruption to the original text."
    )
}

# =========================================================
# SYSTEM INSTRUCTIONS (DETECTOR BYPASS & HUMANIZATION)
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
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))

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
# DOCUMENT IMPORT
# =========================================================

def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    filename = uploaded_file.name.lower()

    if filename.endswith((".txt", ".md")):
        return uploaded_file.getvalue().decode(
            "utf-8", errors="replace"
        )

    if filename.endswith(".docx"):
        try:
            from docx import Document

            document = Document(
                io.BytesIO(uploaded_file.getvalue())
            )

            paragraphs = [
                p.text for p in document.paragraphs
                if p.text.strip()
            ]

            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(
                        " | ".join(cell.text for cell in row.cells)
                    )

            return "\n\n".join(paragraphs)

        except ImportError:
            raise ValueError(
                "DOCX support requires python-docx."
            )

    raise ValueError(
        "Unsupported file format. Use TXT, MD or DOCX."
    )

# =========================================================
# SAFE TEXT CHUNKING
# =========================================================

def split_long_paragraph(
    paragraph: str,
    max_words: int
) -> List[str]:

    sentences = re.split(
        r"(?<=[.!?])\s+",
        paragraph.strip()
    )

    chunks = []
    current = []
    current_count = 0

    for sentence in sentences:
        sentence_words = count_words(sentence)

        if sentence_words > max_words:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_count = 0

            words = sentence.split()

            for i in range(0, len(words), max_words):
                chunks.append(
                    " ".join(words[i:i + max_words])
                )
            continue

        if current_count + sentence_words > max_words:
            chunks.append(" ".join(current))
            current = [sentence]
            current_count = sentence_words
        else:
            current.append(sentence)
            current_count += sentence_words

    if current:
        chunks.append(" ".join(current))

    return chunks

def split_document(
    text: str,
    max_words: int = MAX_CHUNK_WORDS
) -> List[str]:

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]

    chunks = []
    current_paragraphs = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = count_words(paragraph)

        if paragraph_words > max_words:
            if current_paragraphs:
                chunks.append(
                    "\n\n".join(current_paragraphs)
                )
                current_paragraphs = []
                current_words = 0

            chunks.extend(
                split_long_paragraph(paragraph, max_words)
            )
            continue

        if current_words + paragraph_words > max_words:
            chunks.append(
                "\n\n".join(current_paragraphs)
            )
            current_paragraphs = [paragraph]
            current_words = paragraph_words
        else:
            current_paragraphs.append(paragraph)
            current_words += paragraph_words

    if current_paragraphs:
        chunks.append(
            "\n\n".join(current_paragraphs)
        )

    return chunks

# =========================================================
# GEMINI CLIENT
# =========================================================

def create_client(api_key: str):

    http_options = types.HttpOptions(
        timeout=REQUEST_TIMEOUT_MS,
        retry_options=types.HttpRetryOptions(
            attempts=MAX_RETRIES,
            initial_delay=1.0,
            max_delay=8.0,
            http_status_codes=[
                408, 429, 500, 502, 503, 504
            ]
        )
    )

    return genai.Client(
        api_key=api_key,
        http_options=http_options
    )

# =========================================================
# PROMPT BUILDER
# =========================================================

def build_edit_prompt(
    original: str,
    mode: str,
    language: str,
    intensity: int,
    preserve_voice: bool,
    writing_sample: str
) -> str:

    voice_instruction = (
        "Carefully align with the author's personal human writing style."
        if preserve_voice else
        "Adopt an organic, highly unpredictable human writing cadence."
    )

    sample_section = ""

    if writing_sample.strip():
        sample_section = f"""
PERSONAL WRITING SAMPLE REFERENCE:
{writing_sample[:6000]}
Analyze the rhythm, sentence breaks, and vocabulary of this sample and replicate its exact human pattern.
"""

    return f"""
EDITING MODE & STRATEGY:
{mode}

STYLE GUIDANCE:
{MODES[mode]}

TARGET LANGUAGE:
{language}

HUMANIZATION INTENSITY:
{intensity}/10

VOICE & CADENCE:
{voice_instruction}

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
# GEMINI GENERATION
# =========================================================

def generate_text(
    client,
    model: str,
    prompt: str,
    temperature: float = 0.7
) -> str:

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=temperature,
            max_output_tokens=MAX_OUTPUT_TOKENS
        )
    )

    result = response.text

    if not result or not result.strip():
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    return result.strip()

# =========================================================
# DOCUMENT EDITING
# =========================================================

def edit_document(
    client,
    model,
    original,
    mode,
    language,
    intensity,
    preserve_voice,
    writing_sample,
    progress_callback
):

    chunks = split_document(original)

    if not chunks:
        raise ValueError("The document is empty.")

    revised_chunks = []

    for index, chunk in enumerate(chunks):

        prompt = build_edit_prompt(
            original=chunk,
            mode=mode,
            language=language,
            intensity=intensity,
            preserve_voice=preserve_voice,
            writing_sample=writing_sample
        )

        revised = generate_text(
            client=client,
            model=model,
            prompt=prompt
        )

        revised_chunks.append(revised)

        progress_callback(
            index + 1,
            len(chunks),
            f"Humanizing section {index + 1} of {len(chunks)}"
        )

    return "\n\n".join(revised_chunks)

# =========================================================
# CONSISTENCY REVIEW
# =========================================================

def review_document(
    client,
    model,
    original,
    revised
):

    review_prompt = f"""
You are an expert editor ensuring that humanized text did not lose 
its factual accuracy or original meaning. Compare original and revised texts.

Ensure no facts, numbers, names, or citations were altered or deleted.
If any factual error exists, fix it while keeping the humanized structure.

ORIGINAL DOCUMENT:
{original}

REVISED DOCUMENT:
{revised}

Return the final corrected humanized text only.
"""

    return generate_text(
        client,
        model,
        review_prompt,
        temperature=0.1
    )

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("⚙️ Studio Settings")

    try:
        saved_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        saved_key = ""

    api_key = st.text_input(
        "Gemini API Key",
        value=saved_key,
        type="password",
        help="Enter your Gemini API key."
    )

    model_name = st.text_input(
        "Gemini Model",
        value=DEFAULT_MODEL
    )

    st.divider()

    editing_mode = st.selectbox(
        "Writing Style & Strategy",
        list(MODES.keys())
    )

    target_language = st.selectbox(
        "Target Language",
        [
            "English",
            "Azerbaijani",
            "Turkish",
            "Russian",
            "Preserve original language"
        ]
    )

    editing_strength = st.slider(
        "Humanization / Editing Intensity",
        min_value=1,
        max_value=10,
        value=8,
        help="Higher intensity drastically alters sentence structures to defeat AI detectors."
    )

    preserve_voice = st.toggle(
        "Preserve author's writing voice",
        value=True
    )

    run_audit = st.toggle(
        "Run second-pass consistency review (Sərt Audit)",
        value=False,
        help="Aktiv etdikdə fakt yoxlaması aparılır."
    )

    st.divider()

    writing_sample = st.text_area(
        "Personal Writing Sample",
        height=130,
        placeholder="Paste your previous writing sample..."
    )

    st.caption(
        "The sample is used to mimic your personal human writing style."
    )

# =========================================================
# MAIN INPUT AREA
# =========================================================

left, right = st.columns(2)

with left:

    st.subheader("📥 Original Document")

    uploaded_file = st.file_uploader(
        "Upload TXT, MD or DOCX",
        type=["txt", "md", "docx"]
    )

    uploaded_text = ""

    if uploaded_file:
        try:
            uploaded_text = read_uploaded_file(uploaded_file)
        except Exception as error:
            st.error(str(error))

    input_text = st.text_area(
        "Document text",
        value=uploaded_text,
        height=500,
        key="document_input",
        placeholder="Paste your AI-generated or rough text here..."
    )

    stats = get_stats(input_text)

    st.caption(
        f"Words: {stats['Words']} · "
        f"Sentences: {stats['Sentences']} · "
        f"Paragraphs: {stats['Paragraphs']}"
    )

with right:

    st.subheader("📤 Humanized & Refined Document")

    if st.session_state.result:

        st.text_area(
            "Final result",
            value=st.session_state.result,
            height=500,
            key="result_preview"
        )

    else:
        st.info(
            "Your humanized document will appear here."
        )

# =========================================================
# PROCESSING
# =========================================================

st.divider()

if st.button(
    "🚀 START HUMANIZATION & BYPASS REFINEMENT",
    use_container_width=True
):

    if not api_key.strip():
        st.error("Please enter your Gemini API key.")

    elif not input_text.strip():
        st.warning("Please provide a document.")

    else:

        previous_result = st.session_state.result

        progress = st.progress(0)
        status = st.empty()
        start_time = time.time()

        def update_progress(current, total, message):

            percentage = int(
                current / total * 100
            )

            progress.progress(percentage)

            status.info(
                f"{message} · {percentage}% complete"
            )

        try:

            client = create_client(api_key)

            chunks = split_document(input_text)

            st.info(
                f"Document contains {stats['Words']} words "
                f"and will be processed in {len(chunks)} sections."
            )

            revised = edit_document(
                client=client,
                model=model_name,
                original=input_text,
                mode=editing_mode,
                language=target_language,
                intensity=editing_strength,
                preserve_voice=preserve_voice,
                writing_sample=writing_sample,
                progress_callback=update_progress
            )

            audit_result = ""

            if run_audit:

                status.info(
                    "Running factual consistency review..."
                )

                try:
                    audit_result = review_document(
                        client,
                        model_name,
                        input_text,
                        revised
                    )

                    if audit_result.strip():
                        revised = audit_result

                except Exception as audit_error:

                    logger.exception(
                        "Quality review failed"
                    )

                    st.warning(
                        "The review failed. The original humanized "
                        "result has been preserved."
                    )

            elapsed = time.time() - start_time

            if not revised.strip():
                raise RuntimeError(
                    "The final document is empty."
                )

            st.session_state.result = revised
            st.session_state.original = input_text
            st.session_state.processing_time = elapsed
            st.session_state.audit_report = audit_result
            st.session_state.last_error = ""

            st.session_state.history.append({
                "words": count_words(input_text),
                "time": round(elapsed, 2),
                "mode": editing_mode
            })

            progress.progress(100)

            status.success(
                f"Humanization and bypass completed successfully in {elapsed:.1f} seconds."
            )

            st.rerun()

        except Exception as error:

            logger.exception("Document processing failed")

            st.session_state.result = previous_result
            st.session_state.last_error = str(error)

            status.empty()
            progress.empty()

            st.error(
                f"Processing failed: {error}"
            )

# =========================================================
# RESULTS
# =========================================================

if st.session_state.result:

    result = st.session_state.result
    original = st.session_state.original

    st.divider()
    st.header("📊 Document Analysis")

    before = get_stats(original)
    after = get_stats(result)

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Original Words",
        before["Words"]
    )

    m2.metric(
        "Humanized Words",
        after["Words"],
        delta=after["Words"] - before["Words"]
    )

    m3.metric(
        "Original Paragraphs",
        before["Paragraphs"]
    )

    m4.metric(
        "Processing Time",
        f"{st.session_state.processing_time:.1f}s"
    )

    tab1, tab2, tab3 = st.tabs([
        "Final Document",
        "Comparison",
        "Export"
    ])

    with tab1:

        st.text_area(
            "Final editable version",
            value=result,
            height=450
        )

    with tab2:

        diff = difflib.unified_diff(
            original.splitlines(),
            result.splitlines(),
            fromfile="Original",
            tofile="Humanized",
            lineterm=""
        )

        st.code(
            "\n".join(diff),
            language="diff"
        )

    with tab3:

        st.download_button(
            "⬇️ Download TXT",
            data=result.encode("utf-8"),
            file_name="humanized_document.txt",
            mime="text/plain"
        )

        st.download_button(
            "⬇️ Download Markdown",
            data=result.encode("utf-8"),
            file_name="humanized_document.md",
            mime="text/markdown"
        )

        try:
            from docx import Document

            doc = Document()

            for paragraph in result.split("\n"):
                doc.add_paragraph(paragraph)

            buffer = io.BytesIO()
            doc.save(buffer)

            st.download_button(
                "⬇️ Download DOCX",
                data=buffer.getvalue(),
                file_name="humanized_document.docx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                )
            )

        except ImportError:
            st.info(
                "Install python-docx to enable DOCX export."
            )

# =========================================================
# SESSION HISTORY
# =========================================================

if st.session_state.history:

    with st.expander("📚 Processing History"):

        for index, item in enumerate(
            reversed(st.session_state.history[-10:]),
            start=1
        ):

            st.write(
                f"{index}. {item['words']} words · "
                f"{item['time']} seconds · "
                f"{item['mode']}"
            )

st.divider()

st.caption(
    "Professional AI Writing Studio & Bypass | "
    "Powered by Google Gemini | "
    "Designed to maximize human cadence and evade AI detection."
)
