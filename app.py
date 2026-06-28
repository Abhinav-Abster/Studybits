"""
app.py — StudyPlan AI, overhauled UI
"""

import asyncio, json, os, re, uuid
from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from pipeline import root_agent
from tools.pdf_tools import read_pdf_file, sanitize_syllabus_text
from mcp_server.server import save_study_plan, save_user_profile, load_user_profile

APP_NAME = "studyplan_ai"

SAMPLE_SYLLABUS = """Course: Design and Analysis of Algorithms (21CSC204J)
Credit: 4  |  Exam: 100 marks (Part A: 20 MCQ x 1 = 20, Part B: 5 x 16 = 80)

UNIT I — Introduction to Algorithms (16 marks)
  - Divide and Conquer: Merge Sort, Quick Sort, Binary Search
  - Recurrence relations: Master Theorem, Substitution method
  - Time & Space complexity: Big-O, Theta, Omega

UNIT II — Greedy Algorithms (16 marks)
  - Activity Selection, Huffman Coding, Fractional Knapsack
  - Minimum Spanning Tree: Prim's, Kruskal's
  - Dijkstra's Shortest Path

UNIT III — Dynamic Programming (16 marks)
  - Matrix Chain Multiplication, 0/1 Knapsack, LCS
  - Bellman-Ford, Floyd-Warshall

UNIT IV — Backtracking and Branch & Bound (16 marks)
  - N-Queens, Graph Coloring, Hamiltonian Cycle
  - TSP via Branch and Bound

UNIT V — NP-Completeness (16 marks)
  - P, NP, NP-Hard, NP-Complete, Cook's Theorem
  - Approximation and Randomized Algorithms"""


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────────────────────────────────────

def extract_json_substring(text: str) -> str:
    """
    Extracts the first matching JSON block ({...} or [...]) from text,
    robustly handling surrounding text, markdown fences, trailing comments,
    and extra trailing closing braces.
    """
    text = text.strip()
    start_idx = -1
    for i, c in enumerate(text):
        if c in ('{', '['):
            start_idx = i
            break
    if start_idx == -1:
        return text

    brace_count = 0
    in_string = False
    escape = False
    opening_char = text[start_idx]
    closing_char = '}' if opening_char == '{' else ']'

    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if not in_string:
            if c == opening_char:
                brace_count += 1
            elif c == closing_char:
                brace_count -= 1
                if brace_count == 0:
                    return text[start_idx:i+1]
    return text[start_idx:]


async def run_pipeline(syllabus_text, days, hours, user_id):
    session_service = InMemorySessionService()
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id,
        state={"days_until_exam": str(days), "daily_hours": str(hours)},
    )
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
    user_message = types.Content(role="user", parts=[types.Part(text=syllabus_text)])
    responses = {}
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_message):
        if event.author and event.content:
            parts = [p.text for p in event.content.parts if hasattr(p, "text") and p.text]
            text = "".join(parts).strip()
            if text:
                responses[event.author] = text
    if "ScheduleBuilderAgent" in responses:
        clean_schedule_json = extract_json_substring(responses.get("ScheduleBuilderAgent", ""))
        save_study_plan(f"{user_id}_plan.json", clean_schedule_json)
    save_user_profile(user_id, json.dumps({"user_id": user_id, "days_until_exam": days, "daily_hours": hours}))
    return responses


def parse_json_safe(text):
    try:
        clean_text = extract_json_substring(text)
        return json.loads(clean_text)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Renderers
# ─────────────────────────────────────────────────────────────────────────────

def render_empty(icon, title, subtitle):
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                padding:64px 24px;text-align:center;color:#94a3b8;">
      <div style="font-size:3rem;margin-bottom:16px;opacity:0.4">{icon}</div>
      <div style="font-size:1rem;font-weight:600;color:#64748b;margin-bottom:6px">{title}</div>
      <div style="font-size:0.85rem;max-width:320px;line-height:1.5">{subtitle}</div>
    </div>"""


def render_topics(text):
    if not text:
        return render_empty("📋", "Topics will appear here", "Run the pipeline to extract and structure your syllabus topics.")
    data = parse_json_safe(text)
    if not data:
        return f"<pre style='padding:16px;background:#f8fafc;border-radius:8px;font-size:0.82rem;overflow:auto'>{text}</pre>"

    course = data.get("course_name", "Course")
    units  = data.get("units", [])
    notes  = data.get("exam_pattern_notes", "")
    total_units = data.get("total_units", len(units))

    html = f"""
    <div style="padding:4px 0">
      <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:6px">
        <h2 style="margin:0;font-size:1.3rem;font-weight:700;color:#1e293b">{course}</h2>
        <span style="font-size:0.78rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
                     color:#6366f1;background:#eef2ff;padding:3px 10px;border-radius:99px">{total_units} units</span>
      </div>"""
    if notes:
        html += f"<p style='margin:0 0 20px;font-size:0.85rem;color:#64748b;line-height:1.5'>{notes}</p>"

    for unit in units:
        topics = unit.get("topics", [])
        html += f"""
      <div style="margin-bottom:16px;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
        <div style="background:#f8fafc;padding:12px 16px;border-bottom:1px solid #e2e8f0;
                    display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:700;font-size:0.95rem;color:#1e293b">
            Unit {unit.get('unit_number','')} — {unit.get('unit_title','')}
          </span>
          <span style="font-size:0.75rem;color:#94a3b8">{len(topics)} topic{'s' if len(topics)!=1 else ''}</span>
        </div>"""
        for topic in topics:
            marks = topic.get("marks_hint","")
            hrs   = topic.get("estimated_hours","")
            subs  = topic.get("subtopics",[])
            marks_badge = f"<span style='font-size:0.7rem;background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:99px;font-weight:600'>{marks}</span>" if marks and marks!="unknown" else ""
            html += f"""
        <div style="padding:12px 16px;border-bottom:1px solid #f1f5f9">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:{'6px' if subs else '0'}">
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-weight:600;font-size:0.9rem;color:#334155">{topic.get('title','')}</span>
              {marks_badge}
            </div>
            <span style="font-size:0.78rem;color:#94a3b8;white-space:nowrap">{hrs}h</span>
          </div>"""
            if subs:
                html += "<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:6px'>"
                for s in subs:
                    html += f"<span style='font-size:0.75rem;background:#f1f5f9;color:#475569;padding:2px 9px;border-radius:6px'>{s}</span>"
                html += "</div>"
            html += "</div>"
        html += "</div>"
    html += "</div>"
    return html


def render_priority(text):
    if not text:
        return render_empty("🎯", "Priority ranking will appear here", "Topics will be ranked by marks weightage, difficulty, and dependencies.")
    data = parse_json_safe(text)
    if not data:
        return f"<pre style='padding:16px;background:#f8fafc;border-radius:8px;font-size:0.82rem;overflow:auto'>{text}</pre>"

    topics     = data.get("priority_ranked_topics", [])
    quick_wins = set(data.get("quick_wins", []))
    high_risk  = set(data.get("high_risk_topics", []))
    total_hrs  = data.get("total_study_hours_estimate", "?")

    diff_cfg = {
        "Easy":   ("#dcfce7", "#166534"),
        "Medium": ("#fef9c3", "#854d0e"),
        "Hard":   ("#fee2e2", "#991b1b"),
    }

    html = f"""
    <div style="padding:4px 0">
      <div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap">
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 20px;min-width:140px">
          <div style="font-size:1.6rem;font-weight:800;color:#6366f1">{total_hrs}<span style="font-size:0.9rem;font-weight:500;color:#94a3b8">h</span></div>
          <div style="font-size:0.75rem;color:#64748b;margin-top:2px">Total study hours</div>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 20px;min-width:140px">
          <div style="font-size:1.6rem;font-weight:800;color:#10b981">{len(quick_wins)}</div>
          <div style="font-size:0.75rem;color:#64748b;margin-top:2px">Quick wins</div>
        </div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 20px;min-width:140px">
          <div style="font-size:1.6rem;font-weight:800;color:#ef4444">{len(high_risk)}</div>
          <div style="font-size:0.75rem;color:#64748b;margin-top:2px">High risk topics</div>
        </div>
      </div>
      <div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">"""

    for i, t in enumerate(topics):
        tid   = t.get("topic_id","")
        score = t.get("priority_score", 0)
        diff  = t.get("difficulty","")
        rank  = t.get("rank","")
        bg    = "#ffffff" if i % 2 == 0 else "#fafafa"
        dbg, dfg = diff_cfg.get(diff, ("#f1f5f9","#475569"))

        # Score dots
        dots = "".join([
            f"<span style='display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:2px;background:{'#6366f1' if j < score else '#e2e8f0'}'></span>"
            for j in range(10)
        ])

        tags = ""
        if tid in quick_wins:
            tags += "<span style='font-size:0.68rem;background:#dcfce7;color:#166534;padding:2px 7px;border-radius:99px;font-weight:600;margin-left:6px'>Quick win</span>"
        if tid in high_risk:
            tags += "<span style='font-size:0.68rem;background:#fee2e2;color:#991b1b;padding:2px 7px;border-radius:99px;font-weight:600;margin-left:6px'>High risk</span>"

        html += f"""
        <div style="display:grid;grid-template-columns:36px 1fr auto;gap:12px;align-items:start;
                    padding:14px 16px;background:{bg};border-bottom:1px solid #f1f5f9">
          <div style="font-size:1.1rem;font-weight:800;color:#c7d2fe;text-align:center;padding-top:2px">#{rank}</div>
          <div>
            <div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:4px">
              <span style="font-weight:600;font-size:0.92rem;color:#1e293b">{t.get('title','')}</span>{tags}
            </div>
            <div style="font-size:0.78rem;color:#94a3b8;margin-bottom:6px">{t.get('unit','')}</div>
            <div style="font-size:0.75rem;color:#64748b;line-height:1.4">{t.get('priority_reason','')}</div>
          </div>
          <div style="text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:6px;min-width:90px">
            <span style="font-size:0.72rem;font-weight:700;background:{dbg};color:{dfg};padding:2px 9px;border-radius:99px">{diff}</span>
            <div style="line-height:1">{dots}</div>
            <span style="font-size:0.78rem;color:#94a3b8">{t.get('estimated_hours','?')}h</span>
          </div>
        </div>"""

    html += "</div></div>"
    return html


def render_schedule(text):
    if not text:
        return render_empty("📅", "Schedule will appear here", "A day-by-day study calendar will be built from your priority plan.")
    data = parse_json_safe(text)
    if not data:
        return f"<pre style='padding:16px;background:#f8fafc;border-radius:8px;font-size:0.82rem;overflow:auto'>{text}</pre>"

    schedule = data.get("schedule", [])
    warnings = data.get("warnings", [])
    rev_days = set(data.get("revision_days", []))

    html = "<div style='padding:4px 0'>"

    if warnings:
        html += f"""<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;
                               padding:12px 16px;margin-bottom:16px;font-size:0.83rem;color:#92400e">
          {"".join(f"⚠ {w}<br>" for w in warnings)}</div>"""

    for day in schedule:
        is_rev  = day.get("is_revision_day", day.get("day") in rev_days)
        label   = day.get("label", f"Day {day.get('day')}")
        goal    = day.get("daily_goal", "")
        topics  = day.get("topics", [])
        tot_hrs = day.get("total_hours", "?")

        if is_rev:
            card_style = "border:2px solid #a5b4fc;background:linear-gradient(135deg,#eef2ff,#f5f3ff)"
            label_style = "color:#4338ca;font-weight:800"
        else:
            card_style = "border:1px solid #e2e8f0;background:#ffffff"
            label_style = "color:#1e293b;font-weight:700"

        html += f"""
      <div style="{card_style};border-radius:14px;padding:16px 20px;margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
          <div>
            <div style="font-size:0.95rem;{label_style};margin-bottom:3px">{label}</div>
            <div style="font-size:0.82rem;color:#64748b;line-height:1.4">{goal}</div>
          </div>
          <span style="font-size:0.78rem;background:{'#e0e7ff' if is_rev else '#f1f5f9'};
                       color:{'#4338ca' if is_rev else '#64748b'};padding:3px 12px;
                       border-radius:99px;white-space:nowrap;margin-left:12px;font-weight:600">{tot_hrs}h</span>
        </div>"""

        if is_rev:
            html += "<div style='font-size:0.83rem;color:#6366f1;font-weight:500;margin-top:6px'>📖 Full revision day — go through all topics</div>"
        else:
            if topics:
                html += "<div style='margin-top:10px;display:flex;flex-direction:column;gap:6px'>"
                for t in topics:
                    tip = t.get("study_tip","")
                    html += f"""
              <div style="background:#f8fafc;border-radius:8px;padding:10px 12px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <span style="font-size:0.88rem;font-weight:600;color:#334155">{t.get('title','')}</span>
                  <span style="font-size:0.78rem;color:#94a3b8;flex-shrink:0;margin-left:8px">{t.get('hours','?')}h</span>
                </div>"""
                    if tip:
                        html += f"<div style='font-size:0.78rem;color:#6366f1;margin-top:4px'>💡 {tip}</div>"
                    html += "</div>"
                html += "</div>"

        html += "</div>"

    html += "</div>"
    return html


def render_content(text):
    if not text:
        return render_empty("🧠", "Study pack will appear here", "Summaries, key concepts, and MCQs will be generated for every topic.")
    data = parse_json_safe(text)
    if not data:
        return f"<pre style='padding:16px;background:#f8fafc;border-radius:8px;font-size:0.82rem;overflow:auto'>{text}</pre>"

    topics     = data.get("topics", [])
    course     = data.get("course_name", "")
    total_mcqs = data.get("total_mcqs", "?")

    if not topics:
        return render_empty("🧠", "No content generated", "The content agent ran but returned no topics.")

    html = "<div style='padding:4px 0'>"
    if course:
        html += f"""<p style="font-size:0.83rem;color:#94a3b8;margin:0 0 16px">
          {course} · {len(topics)} topics · {total_mcqs} MCQs</p>"""

    for mat in topics:
        title   = mat.get("title","Topic")
        unit    = mat.get("unit","")
        summary = mat.get("summary","")
        keys    = mat.get("key_concepts",[])
        mcqs    = mat.get("mcqs",[])

        html += f"""
      <div style="border:1px solid #e2e8f0;border-radius:14px;margin-bottom:16px;overflow:hidden">
        <div style="background:#f8fafc;padding:14px 18px;border-bottom:1px solid #e2e8f0">
          <div style="font-weight:700;font-size:1rem;color:#1e293b">{title}</div>
          {'<div style="font-size:0.78rem;color:#94a3b8;margin-top:2px">'+unit+'</div>' if unit else ''}
        </div>
        <div style="padding:16px 18px">"""

        if summary:
            lines = [l.strip().lstrip("•-* ").strip() for l in summary.splitlines() if l.strip().lstrip("•-* ").strip()]
            html += "<div style='margin-bottom:14px'>"
            html += "<div style='font-size:0.72rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#94a3b8;margin-bottom:8px'>Study Notes</div>"
            for line in lines:
                html += f"<div style='display:flex;gap:8px;margin-bottom:6px;font-size:0.87rem;color:#334155;line-height:1.5'><span style='color:#6366f1;flex-shrink:0;margin-top:1px'>▸</span><span>{line}</span></div>"
            html += "</div>"

        if keys:
            html += "<div style='margin-bottom:14px'>"
            html += "<div style='font-size:0.72rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#94a3b8;margin-bottom:8px'>Key Concepts</div>"
            html += "<div style='display:flex;flex-wrap:wrap;gap:5px'>"
            for k in keys:
                html += f"<span style='font-size:0.78rem;background:#eef2ff;color:#4338ca;padding:3px 10px;border-radius:6px;font-weight:500'>{k}</span>"
            html += "</div></div>"

        if mcqs:
            html += "<div>"
            html += "<div style='font-size:0.72rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#94a3b8;margin-bottom:10px'>Practice MCQs</div>"
            for i, q in enumerate(mcqs, 1):
                correct = q.get("correct_answer","")
                opts    = q.get("options",{})
                exp     = q.get("explanation","")

                html += f"""
            <div style="background:#f8fafc;border-radius:10px;padding:14px 16px;margin-bottom:10px;border:1px solid #f1f5f9">
              <div style="font-size:0.88rem;font-weight:600;color:#1e293b;margin-bottom:10px;line-height:1.4">
                <span style="color:#6366f1;margin-right:6px">Q{i}.</span>{q.get('question','')}
              </div>
              <div style="display:flex;flex-direction:column;gap:5px">"""

                for letter in ["A","B","C","D"]:
                    opt_text = opts.get(letter,"")
                    if not opt_text:
                        continue
                    is_ans = (letter == correct)
                    if is_ans:
                        opt_style = "background:#dcfce7;border:1px solid #86efac;color:#166534;font-weight:600"
                        prefix    = f"<span style='margin-right:6px;font-weight:800'>✓</span>"
                    else:
                        opt_style = "background:#ffffff;border:1px solid #e2e8f0;color:#475569"
                        prefix    = f"<span style='color:#94a3b8;margin-right:6px;font-weight:600'>{letter}.</span>"
                    html += f"<div style='{opt_style};border-radius:7px;padding:8px 12px;font-size:0.84rem;line-height:1.4'>{prefix}{opt_text}</div>"

                html += "</div>"
                if exp:
                    html += f"<div style='margin-top:10px;font-size:0.8rem;color:#6366f1;background:#eef2ff;border-radius:7px;padding:8px 12px;line-height:1.4'>📖 {exp}</div>"
                html += "</div>"
            html += "</div>"

        html += "</div></div>"

    html += "</div>"
    return html


# ─────────────────────────────────────────────────────────────────────────────
# CSS — clean, warm-neutral base, indigo accent, Inter typography
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Reset Gradio chrome ── */
.gradio-container {
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
  background: #f8fafc !important;
  max-width: 1200px !important;
}
.main { padding: 0 !important; }
footer { display: none !important; }

/* ── Hero header ── */
.sp-hero {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
  border-radius: 16px;
  padding: 32px 36px;
  margin-bottom: 24px;
  color: white;
  position: relative;
  overflow: hidden;
}
.sp-hero::before {
  content: '';
  position: absolute;
  top: -60px; right: -60px;
  width: 220px; height: 220px;
  border-radius: 50%;
  background: rgba(255,255,255,0.04);
}
.sp-hero::after {
  content: '';
  position: absolute;
  bottom: -40px; left: 30%;
  width: 160px; height: 160px;
  border-radius: 50%;
  background: rgba(255,255,255,0.03);
}
.sp-hero-title {
  font-size: 1.8rem;
  font-weight: 800;
  margin: 0 0 6px;
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.sp-hero-sub {
  font-size: 0.88rem;
  color: #a5b4fc;
  margin: 0 0 20px;
  line-height: 1.5;
}
.sp-pipeline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.sp-pill {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: .04em;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  color: #c7d2fe;
  padding: 4px 12px;
  border-radius: 99px;
}
.sp-arrow { color: #6366f1; font-size: 0.85rem; }

/* ── Input card ── */
.sp-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 16px;
}
.sp-section-label {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #94a3b8;
  margin-bottom: 12px;
}

/* ── Generate button ── */
.sp-run-btn {
  background: linear-gradient(135deg, #4338ca, #6366f1) !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  font-size: 0.95rem !important;
  padding: 13px !important;
  color: white !important;
  transition: opacity 0.15s, transform 0.15s !important;
  box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
}
.sp-run-btn:hover {
  opacity: 0.92 !important;
  transform: translateY(-1px) !important;
}

/* ── Status bar ── */
.sp-status textarea {
  font-size: 0.83rem !important;
  color: #475569 !important;
  background: #f8fafc !important;
  border: 1px solid #e2e8f0 !important;
  border-radius: 10px !important;
  font-family: 'Inter', monospace !important;
}

/* ── Agent progress tracker ── */
.sp-progress {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.sp-agent-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 99px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #94a3b8;
}
.sp-agent-step.done {
  background: #eef2ff;
  border-color: #a5b4fc;
  color: #4338ca;
}

/* ── Tab strip ── */
.tab-nav button {
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  border-radius: 8px 8px 0 0 !important;
  padding: 10px 18px !important;
  color: #64748b !important;
}
.tab-nav button.selected {
  color: #4338ca !important;
  border-bottom: 2px solid #6366f1 !important;
}

/* ── Output panels ── */
.sp-output-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0 12px 12px 12px;
  padding: 20px;
  min-height: 320px;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

def build_ui():
    with gr.Blocks(css=CSS, title="StudyPlan AI") as demo:

        # ── Hero ──────────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="sp-hero">
          <div class="sp-hero-title">📚 StudyPlan AI</div>
          <div class="sp-hero-sub">
            Paste your syllabus. Get a prioritized study plan, day-by-day schedule, and practice MCQs — powered by a 4-agent AI pipeline.
          </div>
          <div class="sp-pipeline">
            <span class="sp-pill">Parser</span>
            <span class="sp-arrow">→</span>
            <span class="sp-pill">Prioritizer</span>
            <span class="sp-arrow">→</span>
            <span class="sp-pill">Scheduler</span>
            <span class="sp-arrow">→</span>
            <span class="sp-pill">Content</span>
            <span class="sp-arrow">→</span>
            <span class="sp-pill" style="background:rgba(165,180,252,0.15);color:#e0e7ff">Your Study Plan</span>
          </div>
        </div>
        """)

        # ── Inputs ────────────────────────────────────────────────────────────
        with gr.Row(equal_height=False):
            with gr.Column(scale=3):
                gr.HTML('<div class="sp-section-label">Your syllabus</div>')
                syllabus_input = gr.Textbox(
                    show_label=False,
                    placeholder="Paste your course syllabus here — units, topics, marks distribution...",
                    lines=14,
                    value=SAMPLE_SYLLABUS,
                    elem_classes=["sp-syllabus"],
                )
                pdf_input = gr.File(
                    label="Or upload a PDF (overrides text above)",
                    file_types=[".pdf"],
                    scale=1,
                )

            with gr.Column(scale=1, min_width=240):
                gr.HTML('<div class="sp-section-label">Exam context</div>')
                days_input = gr.Slider(
                    label="Days until exam",
                    minimum=3, maximum=30, step=1, value=7,
                )
                hours_input = gr.Slider(
                    label="Daily study hours",
                    minimum=1.0, maximum=10.0, step=0.5, value=4.0,
                )
                user_input = gr.Textbox(
                    label="Student ID",
                    value="student_001",
                    info="Used to save your plan locally",
                )
                run_btn = gr.Button(
                    "Generate Study Plan ▶",
                    variant="primary",
                    size="lg",
                    elem_classes=["sp-run-btn"],
                )
                status = gr.Textbox(
                    label="Pipeline status",
                    interactive=False,
                    lines=3,
                    elem_classes=["sp-status"],
                )

        # ── Output tabs ───────────────────────────────────────────────────────
        with gr.Tabs(elem_classes=["sp-tabs"]):
            with gr.Tab("📋  Topics"):
                topics_out = gr.HTML(
                    value=render_empty("📋", "Topics will appear here",
                                       "Run the pipeline to extract and structure your syllabus topics."),
                )
            with gr.Tab("🎯  Priority"):
                priority_out = gr.HTML(
                    value=render_empty("🎯", "Priority ranking will appear here",
                                       "Topics will be ranked by marks weightage, difficulty, and dependencies."),
                )
            with gr.Tab("📅  Schedule"):
                schedule_out = gr.HTML(
                    value=render_empty("📅", "Schedule will appear here",
                                       "A day-by-day study calendar will be built from your priority plan."),
                )
            with gr.Tab("🧠  Study Pack"):
                content_out = gr.HTML(
                    value=render_empty("🧠", "Study pack will appear here",
                                       "Summaries, key concepts, and MCQs will be generated for every topic."),
                )

        # ── Logic ─────────────────────────────────────────────────────────────
        def on_run(syllabus_text, pdf_file, days, hours, user_id):
            user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id.strip())[:64] or "student_001"

            if pdf_file is not None:
                result = read_pdf_file(pdf_file.name)
                if not result["success"]:
                    yield f"❌ PDF error: {result['error']}", "", "", "", ""
                    return
                raw = result["text"]
                yield f"📄 PDF read — {result['pages']} pages extracted...", "", "", "", ""
            else:
                raw = syllabus_text

            clean = sanitize_syllabus_text(raw)
            if not clean["success"] or not clean["clean_text"].strip():
                yield "❌ No syllabus text found. Paste your syllabus or upload a PDF.", "", "", "", ""
                return

            yield "⏳ Agent 1/4 — Parsing syllabus structure...", "", "", "", ""

            try:
                loop = asyncio.new_event_loop()
                responses = loop.run_until_complete(
                    run_pipeline(clean["clean_text"], int(days), float(hours), user_id)
                )
                loop.close()
            except Exception as e:
                yield f"❌ Pipeline error: {e}", "", "", "", ""
                return

            topics_html   = render_topics(responses.get("SyllabusParserAgent", ""))
            priority_html = render_priority(responses.get("TopicPrioritizerAgent", ""))
            schedule_html = render_schedule(responses.get("ScheduleBuilderAgent", ""))
            content_html  = render_content(responses.get("ContentGeneratorAgent", ""))

            n = len([v for v in responses.values() if v])
            msg = f"✅ Done — {n} agents completed · plan saved for '{user_id}'"
            if "ContentGeneratorAgent" not in responses:
                msg += "\n⚠ ContentGeneratorAgent had no output — check pipeline wiring"

            yield msg, topics_html, priority_html, schedule_html, content_html

        run_btn.click(
            fn=on_run,
            inputs=[syllabus_input, pdf_input, days_input, hours_input, user_input],
            outputs=[status, topics_out, priority_out, schedule_out, content_out],
        )

    return demo


if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠  GOOGLE_API_KEY not set — add it to your .env file")
    build_ui().launch(server_name="0.0.0.0", server_port=7860, show_error=True)