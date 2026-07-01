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

st.markdown("<div class='main-title'>📝 Nihar's Quiz/Test Generator</div>", unsafe_allow_html=True)
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
        # PDF files
        if uploaded_file.type == "application/pdf" or uploaded_file.name.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(uploaded_file)
            return " ".join([p.extract_text() or "" for p in reader.pages])

        # Word DOCX files
        if uploaded_file.type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword"
        ] or uploaded_file.name.endswith(".docx"):
            from docx import Document
            doc = Document(uploaded_file)
            return " ".join([p.text for p in doc.paragraphs])

        # Plain text files
        if uploaded_file.type == "text/plain" or uploaded_file.name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")

        # Fallback for other formats
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
        # ✅ Properly finished loop
    while len(normalized) < num_q:
        i = len(normalized) + 1
        normalized.append({
            "id": f"Q{i}",
            "question": f"Placeholder question {i} (model produced fewer questions).",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "answer": random.choice(["A", "B", "C", "D"]),
            "hint": "Review the basic idea related to the topic.",
            "explanation": "This is a placeholder explanation because the model did not provide enough questions."
        })
    return normalized

# ---------------- Sidebar: source & settings ----------------
with st.sidebar:
    st.header("📂 Source")
    source_type = st.radio("Choose source type:", ["Topic Name", "File Upload", "Website URL"])
    source_text = ""
    if source_type == "Topic Name":
        source_text = st.text_input("Enter a topic/context:")
    elif source_type == "File Upload":
        uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
        if uploaded_file:
            source_text = safe_extract_text(uploaded_file)
            if source_text.strip():
                st.caption("File parsed; using its content as source.")
            else:
                st.error("Uploaded file could not be parsed. Please check the format or content.")
    else:
        url = st.text_input("Enter a website URL:")
        if url:
            source_text = safe_extract_url(url)
            st.caption("Website text extracted; using it as source.")

    st.header("⚙️ Test Settings")
    num_q = st.selectbox("Number of Questions", [5, 10, 25, 50], index=0)
    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=0)
    ai_assist = st.checkbox("Enable AI Assistant (Hints)", value=True)

    if st.button("🚀 Generate Test"):
        if not source_text or len(source_text.strip()) < 10:
            st.error("Please provide a valid topic, file, or URL with enough content.")
        else:
            st.session_state.questions = generate_quiz_from_source(source_text, num_q, difficulty)
            st.session_state.current_index = 0
            st.session_state.answers = {}
            st.session_state.finished = False
            st.session_state.last_result = None
            st.session_state.test_history.append({
                "source": source_type,
                "difficulty": difficulty,
                "num_q": num_q,
                "preview": [q["question"] for q in st.session_state.questions[:3]]
            })
            st.success("Quiz generated — good luck!")

# ---------------- Main quiz UI ----------------
if st.session_state.questions:
    idx = st.session_state.current_index
    total = len(st.session_state.questions)
    qobj = st.session_state.questions[idx]

    st.progress(idx / total)

    safe_question_html = qobj['question'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f"<div class='question-card'><div style='display:flex;justify-content:space-between;align-items:center'>"
        f"<div><h4 style='margin:0'>Question {idx+1} of {total}</h4>"
        f"<div class='small-muted'>ID: {qobj['id']}</div></div>"
        f"<div><span class='badge'>{difficulty}</span></div></div>"
        f"<div style='margin-top:12px; white-space:pre-wrap; line-height:1.4;'>{safe_question_html}</div></div>",
        unsafe_allow_html=True
    )

    option_letters = ["A", "B", "C", "D"]
    radio_choices = [f"{letter}. {text}" for letter, text in zip(option_letters, qobj["options"])]
    prev = st.session_state.answers.get(idx, None)
    default_index = option_letters.index(prev) if prev in option_letters else 0
    user_choice = st.radio("Choose your answer:", radio_choices, index=default_index, key=f"radio_{idx}")
    selected_letter = user_choice.split(".", 1)[0].strip()
    st.session_state.answers[idx] = selected_letter

    cols = st.columns([1, 1, 1])
    with cols[0]:
        if st.button("⬅️ Prev", disabled=(idx == 0)):
            st.session_state.current_index = max(0, idx - 1)
    with cols[1]:
        if ai_assist and st.button("💡 Hint"):
            st.info(qobj.get("hint", "Try to recall the main concept behind the question."))
    with cols[2]:
        if st.button("➡️ Next", disabled=(idx == total - 1)):
            st.session_state.current_index = min(total - 1, idx + 1)

    if idx == total - 1:
        all_answered = len(st.session_state.answers) == total
        if not all_answered:
            st.warning("Please answer all questions before submitting.")
        else:
            if st.button("✅ Submit Test"):
                correct = 0
                summary = []
                for i, q in enumerate(st.session_state.questions):
                    user_a = st.session_state.answers.get(i, "")
                    correct_a = q["answer"]
                    is_correct = user_a == correct_a
                    if is_correct:
                        correct += 1
                    summary.append({
                        "id": q["id"],
                        "question": q["question"],
                        "user": user_a,
                        "correct": correct_a,
                        "result": is_correct,
                        "explanation": q.get("explanation", "No explanation provided.")
                    })
                wrong = total - correct
                pct = round((correct / total) * 100, 1)
                perf = "Excellent" if pct >= 85 else "Good" if pct >= 65 else "Average" if pct >= 40 else "Needs Improvement"
                st.session_state.finished = True
                st.session_state.last_result = {
                    "total": total, "correct": correct, "wrong": wrong, "pct": pct, "perf": perf, "summary": summary
                }

# ---------------- Results dashboard ----------------
if st.session_state.finished and st.session_state.last_result:
    r = st.session_state.last_result
    st.markdown("<div class='question-card'><h3>📊 Score Dashboard</h3></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Questions", r["total"])
    c2.metric("Correct", r["correct"])
    c3.metric("Wrong", r["wrong"])
    c4.metric("Percentage", f"{r['pct']}%")
    st.markdown(f"**Performance:** {r['perf']}")
    st.markdown("---")
    st.markdown("### Summary (with explanations)")
    for s in r["summary"]:
        mark = "✅" if s["result"] else "❌"
        safe_q_html = s["question"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        st.markdown(f"<div style='white-space:pre-wrap; line-height:1.4;'><strong>{s['id']}</strong> — {safe_q_html}</div>", unsafe_allow_html=True)
        st.markdown(f"- Your answer: **{s['user']}**  |  Correct: **{s['correct']}**  {mark}")
        st.markdown(f"- **Explanation:** {s.get('explanation','No explanation provided.')}")
        st.markdown("")
    if st.button("🔁 Restart Quiz"):
        st.session_state.questions = []
        st.session_state.current_index = 0
        st.session_state.answers = {}
        st.session_state.finished = False
        st.session_state.raw_quiz = ""
        st.session_state.last_result = None

# ---------------- Sidebar: history controls ----------------
with st.sidebar:
    st.header("📜 Test History")
    for i, t in enumerate(st.session_state.test_history):
        st.write(f"Test {i+1}: {t['source']} ({t['difficulty']}, {t['num_q']} Qs)")
        if st.button(f"🗑️ Delete {i+1}", key=f"del_{i}"):
            st.session_state.test_history.pop(i)
    if st.button("🧹 Clear All History"):
        st.session_state.test_history.clear()
