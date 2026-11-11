import streamlit as st
from google import genai
from google.genai import types
import difflib
import re
import io

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Professional AI Writing Studio",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

st.title("✍️ Professional AI Writing Studio")

st.caption(
    "Advanced text refinement, academic editing, "
    "style adaptation and linguistic quality assurance."
)

# =========================================================
# SYSTEM INSTRUCTIONS
# =========================================================

SYSTEM_PROMPT = """
You are an expert multilingual editor, academic writing consultant,
linguist and professional communication specialist.

Your task is to improve the quality of user-provided writing.

CORE PRINCIPLES:

1. MEANING PRESERVATION
Preserve the author's original argument, position, reasoning,
intent and factual claims.

2. NATURAL LANGUAGE
Produce clear, fluent and idiomatic language.
Avoid repetitive sentence constructions, mechanical transitions,
unnecessary verbosity and generic expressions.

3. SENTENCE VARIATION
Use a natural mixture of short, medium and longer sentences.
Vary sentence openings where appropriate.
Do not introduce artificial irregularity.

4. VOCABULARY
Choose precise vocabulary appropriate to the subject,
audience, language and writing context.
Do not replace simple words with unnecessarily complicated ones.

5. PARAGRAPH STRUCTURE
Improve logical connections between sentences and paragraphs.
Remove repetition without removing important arguments.

6. FACTUAL INTEGRITY
Never invent statistics, quotations, research findings,
references, sources, authors or historical information.
Preserve names, dates, numbers and technical terminology.

7. CITATIONS
Preserve all existing citations and references.
Never fabricate bibliographic information.
Do not attribute claims to sources that were not provided.

8. AUTHOR VOICE
Retain the author's intended personality, perspective,
level of formality and rhetorical approach.

9. ACADEMIC INTEGRITY
Do not conceal authorship, fabricate research or misrepresent
the origin of ideas. Focus on legitimate editorial improvement.

10. OUTPUT
Return the revised text only.
Do not include explanations unless explicitly requested.
Do not add an introduction or conclusion that was absent
from the original unless necessary for coherence.
"""

# =========================================================
# EDITING MODES
# =========================================================

MODES = {
    "Academic Research": """
Use formal academic language.
Prioritize conceptual precision, logical argumentation,
analytical depth and coherent paragraph development.
Preserve the author's academic level.
Avoid unnecessarily complicated vocabulary.
""",

    "Academic Essay": """
Improve argumentative clarity and critical analysis.
Strengthen topic sentences, transitions and evidence integration.
Maintain a natural university-student academic voice.
""",

    "Journalistic": """
Use engaging, precise and accessible language.
Prioritize readability, concrete details and natural rhythm.
Avoid sensationalism and unsupported claims.
""",

    "Professional Communication": """
Use polished professional language.
Prioritize clarity, conciseness, credibility and readability.
""",

    "Creative Writing": """
Preserve the author's creative intent.
Improve imagery, rhythm, vocabulary and narrative flow.
Avoid generic expressions and unnecessary embellishment.
""",

    "Natural English": """
Use idiomatic, fluent contemporary English.
Prioritize natural collocations, grammatical accuracy
and clear expression without changing the author's meaning.
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
        "Writing Style",
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
        "Editing Intensity",
        1, 10, 6,
        help="Controls the extent of legitimate linguistic and structural editing."
    )

    preserve_voice = st.toggle(
        "Preserve author's writing voice",
        value=True
    )

    fact_check = st.toggle(
        "Run second-pass consistency review",
        value=True
    )

    st.divider()

    st.subheader("Personal Writing Sample")

    writing_sample = st.text_area(
        "Optional: Paste your own writing sample",
        height=140,
        placeholder="Your previous writing sample..."
    )

    st.caption(
        "The sample is used only to guide tone and writing style."
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
        "Carefully preserve the author's writing voice."
        if preserve else
        "Prioritize the selected professional writing style."
    )

    sample_instruction = ""

    if sample.strip():
        sample_instruction = f"""
WRITING STYLE REFERENCE:

Use the following sample only to understand the author's
general vocabulary, tone, sentence preferences and voice.

Do not copy its content.

{sample}
"""

    return f"""
EDITING MODE:
{mode}

STYLE GUIDANCE:
{MODES[mode]}

TARGET LANGUAGE:
{language}

EDITING INTENSITY:
{intensity}/10

VOICE:
{voice_instruction}

{sample_instruction}

EDITING REQUIREMENTS:

- Improve grammar and syntax.
- Improve clarity and coherence.
- Remove unnecessary repetition.
- Improve transitions.
- Preserve all substantive arguments.
- Preserve citations, quotations and factual details.
- Do not invent evidence.
- Do not artificially increase text length.
- Maintain the original intended meaning.

ORIGINAL TEXT:

<original_text>
{original}
</original_text>

Return the complete revised text.
"""

# =========================================================
# SECOND-PASS QUALITY CONTROL
# =========================================================

def quality_review(client, model, original, revised):

    review_prompt = f"""
You are an independent academic editor performing
a factual and semantic consistency review.

Compare the original and revised texts.

Check for:

1. Missing arguments.
2. Changed factual claims.
3. Altered numbers, dates or names.
4. Missing citations.
5. Modified quotations.
6. Unsupported additions.
7. Incorrect terminology.
8. Meaning-changing grammatical edits.

If you find a clear substantive error, correct it.

Do not introduce stylistic changes simply for variety.
Do not add new information.

ORIGINAL:
{original}

REVISED:
{revised}

Return the complete corrected revised text only.
"""

    response = client.models.generate_content(
        model=model,
        contents=review_prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=16000
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
        placeholder="Paste your document here...",
        key="original_text"
    )

    original_stats = readability_stats(input_text)

    st.caption(
        f"Words: {original_stats['Words']} | "
        f"Sentences: {original_stats['Sentences']} | "
        f"Paragraphs: {original_stats['Paragraphs']}"
    )

with col2:

    st.subheader("📤 Refined Document")

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
            "Your refined document will appear here."
        )

# =========================================================
# PROCESSING
# =========================================================

st.divider()

process = st.button(
    "🚀 START ADVANCED TEXT REFINEMENT",
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
                "Stage 1/2: Performing advanced linguistic editing..."
            ):

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.55,
                        max_output_tokens=16000
                    )
                )

                revised_text = response.text

                if not revised_text:
                    raise ValueError(
                        "The model returned an empty response."
                    )

            if fact_check:

                with st.spinner(
                    "Stage 2/2: Checking semantic and factual consistency..."
                ):

                    revised_text = quality_review(
                        client,
                        model_name,
                        input_text,
                        revised_text
                    )

            st.session_state.result = revised_text

            st.success(
                "Text refinement completed successfully."
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

        st.button(
            "Copy-ready text",
            on_click=lambda: st.session_state.update(
                copy_notice="Use the download option below to save your text."
            )
        )

        if st.session_state.get("copy_notice"):
            st.info(st.session_state.copy_notice)

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
            file_name="refined_document.txt",
            mime="text/plain",
            use_container_width=True
        )

        st.download_button(
            "⬇️ Download Markdown",
            data=result,
            file_name="refined_document.md",
            mime="text/markdown",
            use_container_width=True
        )

st.divider()

st.caption(
    "Professional AI Writing Studio | "
    "Powered by Google Gemini | "
    "Editorial quality assurance, not an AI detector bypass guarantee."
)
