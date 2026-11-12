from __future__ import annotations

import io
import re
import time
import random
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
from google import genai
from google.genai import types

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Fast AI Writing Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

DEFAULT_MODEL = "gemini-2.5-flash"  
MAX_CHUNK_WORDS = 4000
MAX_RETRIES = 5
REQUEST_TIMEOUT_MS = 60_000

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
    max-width: 1400px;
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
}
.stButton button {
    width: 100%;
    min-height: 44px;
    border-radius: 10px;
    font-weight: 650;
    background: linear-gradient(120deg,#6366f1,#a855f7);
    color: white;
    border: none;
}
</style>
""", unsafe_allow_html=True)

st.title("⚡ Fast AI Writing Studio & Humanizer")
st.caption("Optimized for Stability · Zero 503 Errors · High Speed")

# =========================================================
# SESSION STATE
# =========================================================

if "result" not in st.session_state:
    st.session_state.result = ""
if "processing_time" not in st.session_state:
    st.session_state.processing_time = 0.0

MODES = {
    "Academic Research (Natural Flow)": "Use rigorous academic phrasing while maintaining natural human rhythm and variable sentence length.",
    "Academic Essay (Student Voice)": "Write in a natural, authentic university student voice avoiding robotic AI syntax.",
    "Professional Communication": "Use polished, natural corporate writing that sounds completely human.",
    "Light Proofreading": "Correct grammar, spelling and punctuation with minimal disruption to the original text."
}

SYSTEM_PROMPT = """
You are an expert human writer and editor. Your objective is to rewrite and humanize the provided text so that it reads naturally, eliminating repetitive robotic patterns and ensuring high readability. Return the revised text only without introductory or concluding remarks.
"""

# =========================================================
# UTILITIES
# =========================================================

def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, re.UNICODE))

def read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    if uploaded_file.name.endswith((".txt", ".md")):
        return uploaded_file.getvalue().decode("utf-8", errors="replace")
    elif uploaded_file.name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(uploaded_file.getvalue()))
            return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except ImportError:
            raise ValueError("python-docx kitabxanası quraşdırılmayıb.")
    return ""

def split_document(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = []
    current_words = 0
    for p in paragraphs:
        p_words = count_words(p)
        if current_words + p_words > max_words and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_words = p_words
        else:
            current.append(p)
            current_words += p_words
    if current:
        chunks.append("\n\n".join(current))
    return chunks if chunks else [text]

def generate_text(client, model: str, prompt: str) -> str:
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=8192
                )
            )
            if response.text:
                return response.text.strip()
        except Exception as e:
            last_error = e
            msg = str(e).upper()
            if "503" in msg or "UNAVAILABLE" in msg or "429" in msg:
                delay = (2 ** attempt) + random.uniform(1, 3)
                time.sleep(delay)
                continue
            raise e
    raise RuntimeError(f"API sorğusu uğursuz oldu: {last_error}")

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.header("Tənzimləmələr")
    api_key = st.text_input("Gemini API Key", type="password", value=st.secrets.get("GEMINI_API_KEY", ""))
    model_name = st.text_input("Model", value=DEFAULT_MODEL)
    editing_mode = st.selectbox("Rejim", list(MODES.keys()))
    target_lang = st.selectbox("Dil", ["English", "Azerbaijani", "Turkish", "Russian"])

# =========================================================
# MAIN UI
# =========================================================

col1, col2 = st.columns(2)

with col1:
    st.subheader("📥 Orijinal Mətn")
    uploaded_file = st.file_uploader("Fayl yüklə (.txt, .docx)", type=["txt", "md", "docx"])
    file_text = read_uploaded_file(uploaded_file) if uploaded_file else ""
    input_text = st.text_area("Və ya mətni bura yapışdırın:", value=file_text, height=400)

with col2:
    st.subheader("📤 Nəticə")
    st.text_area("İşlənmiş mətn", value=st.session_state.result, height=400, key="res_area")

st.divider()

if st.button("🚀 PROSESİ BAŞLAT", use_container_width=True):
    if not api_key.strip():
        st.error("Zəhmət olmasa API açarını daxil edin.")
    elif not input_text.strip():
        st.error("Mətn daxil edilməyib.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_t = time.time()

        try:
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
            chunks = split_document(input_text)
            processed_chunks = []

            for i, chunk in enumerate(chunks):
                status_text.info(f"Hissə işlənir: {i+1} / {len(chunks)}")
                prompt = f"Stil: {MODES[editing_mode]}\nDil: {target_lang}\n\nMətn:\n{chunk}"
                res = generate_text(client, model_name, prompt)
                processed_chunks.append(res)
                progress_bar.progress((i + 1) / len(chunks))

            final_output = "\n\n".join(processed_chunks)
            st.session_state.result = final_output
            st.session_state.processing_time = time.time() - start_t

            status_text.success(f"Tamamlandı! Vaxt: {st.session_state.processing_time:.1f} san.")
            st.rerun()

        except Exception as e:
            status_text.empty()
            progress_bar.empty()
            st.error(f"Xəta baş verdi: {e}")

if st.session_state.result:
    st.download_button("📥 Nəticəni .txt olaraq yüklə", data=st.session_state.result.encode("utf-8"), file_name="netice.txt", mime="text/plain")
