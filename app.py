import streamlit as st
from google import genai
from google.genai import types
import difflib
import re

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Professional AI Writing Studio & Bypass",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Google-un tələb etdiyi və aktiv olan model adı
MODEL_OPTIONS = [
    "gemini-3.8-flash",
]

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
    padding-top: 2rem;
    max-width: 1500px;
}
section[data-testid="stSidebar"] {
    background: #101522;
}
.stTextArea textarea {
    background: #111827 !important;
    color: #f9fafb !important;
    border: 1px solid #374151 !important;
    border-radius: 12px !important;
    font-size: 15px !important;
}
.stButton button {
    width: 100%;
    min-height: 48px;
    border-radius: 10px;
    font-weight: 700;
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
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #293449;
}
</style>
""", unsafe_allow_html=True)

st.title("✍️ Professional AI Writing Studio & Detector Bypass")

st.caption(
    "Advanced text humanization, Turnitin & GPTZero evasion, "
    "style adaptation and linguistic quality assurance."
)

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
- Do not make the text overly robotic or artificially sophisticated 
  with obscure vocabulary; focus entirely on authentic human voice rhythm.

5. OUTPUT
- Return the revised humanized text only. 
- Do not include meta-commentary, explanations, introductions, or conclusions.
"""

# =========================================================
# EDITING MODES
# =========================================================

MODES = {
    "Academic Research (Bypass Focus)": """
Use rigorous academic phrasing while maintaining high human perplexity. 
Break predictable academic patterns to slip past Turnitin and GPTZero 
without losing scholarly depth.
""",

    "Academic Essay (Student Voice)": """
Write in a natural, authentic undergraduate/graduate student voice. 
Avoid over-polished, robotic AI syntax. Use organic reasoning flows.
""",

    "Journalistic": """
Use engaging, sharp, human journalistic rhythm. 
Prioritize variable sentence cadence and natural storytelling flow.
""",

    "Professional Communication": """
Use polished, natural corporate or professional writing 
that sounds completely written by an experienced human specialist.
""",

    "Creative Writing": """
Maximize narrative flow, emotional resonance, and stylistic unpredictability. 
Completely eradicate machine-generated formatting.
""",

    "Natural English": """
Ensure maximum idiomatic fluency and human-like cadence 
while strictly maintaining original meaning.
"""
}

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("⚙️ Studio Settings")

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=""
    )

    model_name = st.selectbox(
        "AI Model",
        MODEL_OPTIONS
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
        1, 10, 8,
        help="Higher intensity drastically alters sentence structures to defeat AI detectors."
    )

    preserve_voice = st.toggle(
        "Preserve author's writing voice",
        value=True
    )

    # Sürətli işləməsi üçün default olaraq False təyin edildi
    fact_check = st.toggle(
        "Run second-pass consistency review (Sərt Audit)",
        value=False,
        help="Aktiv etdikdə fakt yoxlaması aparılır, lakin proses bir qədər uzana bilər."
    )

    st.divider()

    st.subheader("Personal Writing Sample")

    writing_sample = st.text_area(
        "Optional: Paste your own writing sample",
        height=140,
        placeholder="Your previous writing sample..."
    )

    st.caption(
        "The sample is used to mimic your personal human writing style."
    )

# =========================================================
# TEXT ANALYSIS
# =========================================================

def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text))

def sentence_count(text):
    return len(re.findall(r"[.!?]+", text))

def paragraph_count(text):
    return len([p for p in text.split("\n") if p.strip()])

def readability_stats(text):
    return {
        "Words": word_count(text),
        "Sentences": sentence_count(text),
        "Paragraphs": paragraph_count(text),
        "Characters": len(text)
    }

# =========================================================
# PROMPT BUILDER
# =========================================================

def build_prompt(
    original,
    mode,
    language,
    intensity,
    preserve,
    sample
):

    voice_instruction = (
        "Carefully align with the author's personal human writing style."
        if preserve else
        "Adopt an organic, highly unpredictable human writing cadence."
    )

    sample_instruction = ""

    if sample.strip():
        sample_instruction = f"""
PERSONAL WRITING SAMPLE REFERENCE:
Analyze the rhythm, sentence breaks, and vocabulary of this sample 
and replicate its exact human pattern:
{sample}
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

{sample_instruction}

BYPASS INSTRUCTIONS:
- Smash predictable sentence patterns to beat Turnitin and GPTZero.
- Vary sentence length aggressively (mix 5-word sentences with 35-word complex sentences).
- Eliminate all robotic AI phrasing and generic transition words.
- Keep all factual claims, data points, and citations fully intact.

ORIGINAL TEXT:

<original_text>
{original}
</original_text>

Return the complete humanized text.
"""

# =========================================================
# SECOND-PASS QUALITY CONTROL
# =========================================================

def quality_review(client, model, original, revised):

    review_prompt = f"""
You are an expert editor ensuring that humanized text did not lose 
its factual accuracy or original meaning. Compare original and revised texts.

Ensure no facts, numbers, names, or citations were altered or deleted.
If any factual error exists, fix it while keeping the humanized structure.

ORIGINAL:
{original}

REVISED:
{revised}

Return the final corrected humanized text only.
"""

    response = client.models.generate_content(
        model=model,
        contents=review_prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8000
        )
    )

    return response.text

# =========================================================
# MAIN INTERFACE
# =========================================================

col1, col2 = st.columns(2)

with col1:

    st.subheader("📥 Original Document")

    input_text = st.text_area(
        "Original text",
        height=520,
        placeholder="Paste your AI-generated or rough text here...",
        key="original_text"
    )

    original_stats = readability_stats(input_text)

    st.caption(
        f"Words: {original_stats['Words']} | "
        f"Sentences: {original_stats['Sentences']} | "
        f"Paragraphs: {original_stats['Paragraphs']}"
    )

with col2:

    st.subheader("📤 Humanized & Refined Document")

    if "result" not in st.session_state:
        st.session_state.result = ""

    result_placeholder = st.empty()

    if st.session_state.result:
        result_placeholder.text_area(
            "Edited text",
            value=st.session_state.result,
            height=520,
            key="result_display"
        )
    else:
        result_placeholder.info(
            "Your humanized document will appear here."
        )

# =========================================================
# PROCESSING
# =========================================================

st.divider()

process = st.button(
    "🚀 START HUMANIZATION & BYPASS REFINEMENT",
    use_container_width=True
)

if process:

    if not api_key.strip():
        st.error("Please enter your Gemini API key.")

    elif not input_text.strip():
        st.warning("Please provide an original document.")

    else:

        try:

            client = genai.Client(api_key=api_key)

            prompt = build_prompt(
                original=input_text,
                mode=editing_mode,
                language=target_language,
                intensity=editing_strength,
                preserve=preserve_voice,
                sample=writing_sample
            )

            with st.spinner(
                "Humanizing text and restructuring sentences for detector bypass..."
            ):

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                        max_output_tokens=8000
                    )
                )

                revised_text = response.text

                if not revised_text:
                    raise ValueError(
                        "The model returned an empty response."
                    )

            if fact_check:

                with st.spinner(
                    "Performing factual consistency review..."
                ):

                    revised_text = quality_review(
                        client,
                        model_name,
                        input_text,
                        revised_text
                    )

            st.session_state.result = revised_text

            st.success(
                "Text humanization and bypass completed successfully."
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"Processing error: {str(e)}"
            )

# =========================================================
# RESULTS & EXPORT
# =========================================================

if st.session_state.result:

    result = st.session_state.result

    st.divider()

    st.header("📊 Document Analysis")

    before = readability_stats(input_text)
    after = readability_stats(result)

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Original Words",
        before["Words"]
    )

    m2.metric(
        "Revised Words",
        after["Words"],
        delta=after["Words"] - before["Words"]
    )

    m3.metric(
        "Original Paragraphs",
        before["Paragraphs"]
    )

    m4.metric(
        "Revised Paragraphs",
        after["Paragraphs"],
        delta=after["Paragraphs"] - before["Paragraphs"]
    )

    tab1, tab2, tab3 = st.tabs([
        "Final Text",
        "Text Comparison",
        "Export"
    ])

    with tab1:

        st.text_area(
            "Final version",
            value=result,
            height=450
        )

    with tab2:

        st.subheader("Original vs Revised")

        diff = list(difflib.unified_diff(
            input_text.splitlines(),
            result.splitlines(),
            fromfile="Original",
            tofile="Revised",
            lineterm=""
        ))

        st.code(
            "\n".join(diff),
            language="diff"
        )

    with tab3:

        st.download_button(
            "⬇️ Download TXT",
            data=result,
            file_name="humanized_document.txt",
            mime="text/plain",
            use_container_width=True
        )

        st.download_button(
            "⬇️ Download Markdown",
            data=result,
            file_name="humanized_document.md",
            mime="text/markdown",
            use_container_width=True
        )

st.divider()

st.caption(
    "Professional AI Writing Studio & Bypass | "
    "Powered by Google Gemini | "
    "Designed to maximize human cadence and evade AI detection."
)
