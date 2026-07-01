# Nihar's Quiz/Test Generator — Complete App (file upload fixed)
# Requirements: streamlit, python-dotenv, requests, beautifulsoup4, PyPDF2, python-docx, pandas, python-pptx, langchain_mistralai
# Keep under ~500 lines

import streamlit as st
from dotenv import load_dotenv
import os
import json
import random
import requests
from bs4 import BeautifulSoup
from langchain_mistralai import ChatMistralAI

# ---------------- Model ----------------
load_dotenv()
API_KEY = os.getenv("MISTRAL_API_KEY")
model = ChatMistralAI(model="mistral-small-2506", temperature=0.7)

# ---------------- Page config & CSS ----------------
st.set_page_config(page_title="Quiz Test Generator", page_icon="📝", layout="wide")

st.markdown(
    """
    <style>
    :root{--bg:#2c3e50;--card:#34495e;--accent:#1abc9c;--muted:#bdc3c7;--text:#ecf0f1;}
    body { background:var(--bg); color:var(--text); font-family: 'Segoe UI', sans-serif; }
    .main-title{font-size:38px;font-weight:700;text-align:center;color:var(--text);margin:6px 0;}
    .subtitle{font-size:16px;text-align:center;color:var(--muted);margin-bottom:18px;}
    .question-card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.02));
                   border-left:6px solid var(--accent); padding:18px; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.35);}
    .option-row{display:flex;align-items:center;gap:12px;padding:10px;border-radius:10px;margin:8px 0;background:#2f3f4f;}
    .option-letter{min-width:44px;height:44px;border-radius:8px;background:var(--accent);display:flex;align-items:center;justify-content:center;font-weight:700;color:#042;flex-shrink:0;}
    .option-text{flex:1;color:var(--text);font-size:15px;}
    .small-muted{color:var(--muted);font-size:13px;}
    .badge{padding:6px 10px;border-radius:999px;background:#e8f8f5;color:#006b5a;font-weight:600;font-size:13px;}
    .controls{display:flex;gap:10px;align-items:center;}
    .hint-box{background:#1f2b33;padding:12px;border-radius:8px;color:var(--muted);margin-top:8px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='main-title'>📝 Beginner's Quiz/Test Generator</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Choose your source, customize settings, and track history.</div>", unsafe_allow_html=True)

# ---------------- Session defaults ----------------
if "test_history" not in st.session_state:
    st.session_state.test_history = []
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "finished" not in st.session_state:
    st.session_state.finished = False
if "raw_quiz" not in st.session_state:
    st.session_state.raw_quiz = ""
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# ---------------- Helpers: extract text ----------------
def safe_extract_text(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf" or uploaded_file.name.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(uploaded_file)
            return " ".join([p.extract_text() or "" for p in reader.pages])

        if uploaded_file.type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ] or uploaded_file.name.endswith(".docx"):
            from docx import Document
            doc = Document(uploaded_file)
            return " ".join([p.text for p in doc.paragraphs])

        if uploaded_file.type == "text/plain" or uploaded_file.name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")

        # fallback for other formats
        return uploaded_file.read().decode("utf-8", errors="ignore")

    except Exception as e:
        st.error(f"File parsing failed: {e}")
        return ""

def safe_extract_url(url):
    try:
        r = requests.get(url, timeout=8)
        soup = BeautifulSoup(r.content, "html.parser")
        for s in soup(["script", "style", "noscript"]):
            s.decompose()
        text = soup.get_text(separator=" ")
        return " ".join(text.split())
    except Exception as e:
        return f"Could not fetch URL: {e}"

# ---------------- Quiz generation & parsing ----------------
def build_generation_prompt(source_text, num_q, difficulty):
    diff_map = {
        "Easy": "simple, short questions for beginners; direct factual answers",
        "Medium": "moderate complexity; require reasoning and short explanation",
        "Hard": "challenging questions that require deeper understanding and multi-step reasoning"
    }
    diff_desc = diff_map.get(difficulty, "mixed difficulty")
    prompt = (
        f"Generate exactly {num_q} multiple-choice questions based on the following source.\n"
        f"Difficulty: {difficulty} ({diff_desc}).\n"
        f"Source excerpt:\n{source_text[:4000]}\n\n"
        "Return valid JSON only. Format:\n"
        '{"questions":[{"id":"Q1","question":"...","options":["optA","optB","optC","optD"],"answer":"B","hint":"...","explanation":"..."}]}\n'
        "Hints must be 1-2 concise sentences and must NOT reveal the answer.\n"
        "Each question object must include an 'explanation' field (1-2 sentences) that briefly explains why the correct option is correct.\n"
        "Ensure unique questions, exactly 4 options each, one correct option, and shuffle options.\n"
    )
    return prompt

def parse_model_quiz(text):
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        if isinstance(data, list):
            return data
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
                if "questions" in data:
                    return data["questions"]
            except Exception:
                pass
    return []

def generate_quiz_from_source(source_text, num_q, difficulty):
    prompt = build_generation_prompt(source_text, num_q, difficulty)
    resp = model.invoke(prompt)
    raw = resp.content
    st.session_state.raw_quiz = raw
    questions = parse_model_quiz(raw)
    normalized = []
    seen = set()
    for q in questions:
        if len(normalized) >= num_q:
            break
        qtext = q.get("question", "").strip()
        opts = q.get("options") or []
        if not qtext or qtext in seen or len(opts) != 4:
            continue
        ans = q.get("answer", "A")
        if ans not in ("A", "B", "C", "D"):
            ans = "A"
        hint = q.get("hint", "").strip() or "Think about the main concept referenced in the question."
        explanation = q.get("explanation", "").strip() or "Brief explanation not provided by model."
        original_correct_text = opts[ord(ans) - 65] if 0 <= (ord(ans) - 65) < 4 else opts[0]
        zipped = list(zip(["A", "B", "C", "D"], opts))
        random.shuffle(zipped)
        new_opts = [t for _, t in zipped]
        new_letter = None
        for i, txt in enumerate(new_opts):
            if txt.strip() == original_correct_text.strip():
                new_letter = ["A", "B", "C", "D"][i]
                break
        if new_letter is None:
            new_letter = random.choice(["A", "B", "C", "D"])
        normalized.append({
            "id": q.get("id", f"Q{len(normalized)+1}"),
            "question": qtext,
            "options": new_opts,
            "answer": new_letter,
            "hint": hint,
            "explanation": explanation
        })
        seen.add(qtext)
    while len(normalized) < num
