"""
run.py

CLI test runner for the StudyPlan pipeline (Day 3 version).

Usage:
    python run.py                                  # sample syllabus, 7 days, 4 hrs/day
    python run.py --days 14 --hours 3              # custom exam context
    python run.py --pdf data/my.pdf --days 5       # real PDF
    python run.py --user student_42                # load saved profile from MCP server

Reads GOOGLE_API_KEY from .env automatically.
"""

import asyncio
import json
import os
import sys
import argparse

from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from pipeline import root_agent
from tools.pdf_tools import read_pdf_file, sanitize_syllabus_text

# ── MCP server tools (called directly here in run.py for saving output) ────────
# Note: agents access MCP via MCPToolset; run.py uses the functions directly
# since it's the orchestration layer, not an agent itself.
sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.server import save_study_plan, save_user_profile, load_user_profile

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME   = "studyplan_ai"
USER_ID    = "student_001"
SESSION_ID = "session_001"

SAMPLE_SYLLABUS = """
Course: Design and Analysis of Algorithms (21CSC204J)
Credit: 4  |  Exam: 100 marks (Part A: 20 MCQ x 1 = 20, Part B: 5 x 16 = 80)

UNIT I — Introduction to Algorithms (16 marks)
  - Algorithm design paradigms: Divide and Conquer
  - Merge Sort, Quick Sort, Binary Search
  - Recurrence relations: Substitution, Master Theorem
  - Time & Space complexity: Big-O, Theta, Omega

UNIT II — Greedy Algorithms (16 marks)
  - Greedy method strategy
  - Activity Selection Problem
  - Huffman Coding
  - Fractional Knapsack
  - Minimum Spanning Tree: Prim's, Kruskal's
  - Dijkstra's Shortest Path Algorithm

UNIT III — Dynamic Programming (16 marks)
  - Principle of optimality
  - Matrix Chain Multiplication
  - 0/1 Knapsack Problem
  - Longest Common Subsequence (LCS)
  - Bellman-Ford, Floyd-Warshall

UNIT IV — Backtracking and Branch & Bound (16 marks)
  - N-Queens Problem
  - Graph Coloring, Hamiltonian Cycle
  - Branch and Bound: 0/1 Knapsack, TSP

UNIT V — NP-Completeness (16 marks)
  - P, NP, NP-Hard, NP-Complete
  - Cook's Theorem, 3-SAT, Clique, Vertex Cover
  - Approximation and Randomized Algorithms
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_syllabus_text(args) -> str:
    if args.pdf:
        print(f"📄 Reading PDF: {args.pdf}")
        result = read_pdf_file(args.pdf)
        if not result["success"]:
            print(f"❌ PDF Error: {result['error']}")
            sys.exit(1)
        raw = result["text"]
        print(f"   → {result['pages']} pages extracted")
    elif args.text:
        raw = args.text
    else:
        print("📝 Using built-in sample syllabus (DAA course)")
        raw = SAMPLE_SYLLABUS

    clean = sanitize_syllabus_text(raw)
    if clean["warning"]:
        print(f"⚠️  {clean['warning']}")
    return clean["clean_text"]


def sep(title: str):
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")


def try_pretty_json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), indent=2)
    except Exception:
        return text


# ── Main ───────────────────────────────────────────────────────────────────────

async def main(args):
    syllabus_text = get_syllabus_text(args)

    # ── Load or build user profile via MCP server ──────────────────────────────
    profile_result = load_user_profile(args.user)
    profile = profile_result["profile"]

    # CLI args override saved profile
    days  = args.days  if args.days  else profile.get("days_until_exam", 7)
    hours = args.hours if args.hours else profile.get("daily_hours", 4.0)

    print(f"\n👤 Student profile: {args.user}")
    print(f"   Days until exam : {days}")
    print(f"   Daily hours     : {hours}")

    # Save updated profile back via MCP
    save_user_profile(args.user, json.dumps({
        "user_id": args.user,
        "days_until_exam": days,
        "daily_hours": hours,
    }))

    # ── ADK session with pre-populated state ───────────────────────────────────
    # Inject days_until_exam and daily_hours into session.state so
    # ScheduleBuilderAgent can read them as {days_until_exam} / {daily_hours}
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={
            "days_until_exam": str(days),
            "daily_hours": str(hours),
        },
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part(text=syllabus_text)],
    )

    sep("🤖 Running StudyPlan Pipeline (Day 3)")
    print("Agents: Parser → Prioritizer → ScheduleBuilder")
    print("(~30-45 seconds — three Gemini calls)\n")

    final_responses = {}

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=user_message,
    ):
        if event.author and event.content:
            parts = [p.text for p in event.content.parts if hasattr(p, "text") and p.text]
            if parts:
                text = "".join(parts).strip()
                if text:
                    final_responses[event.author] = text
                    print(f"✅ [{event.author}] done ({len(text)} chars)")

    # ── Print results ──────────────────────────────────────────────────────────
    for agent_name, title in [
        ("SyllabusParserAgent",   "📋 PARSER — Structured Topics"),
        ("TopicPrioritizerAgent", "🎯 PRIORITIZER — Ranked Topics"),
        ("ScheduleBuilderAgent",  "📅 SCHEDULE — Day-by-Day Plan"),
    ]:
        sep(title)
        if agent_name in final_responses:
            print(try_pretty_json(final_responses[agent_name]))
        else:
            print("(No output — check GOOGLE_API_KEY)")

    # ── Save final plan via MCP server ─────────────────────────────────────────
    if "ScheduleBuilderAgent" in final_responses:
        sep("💾 Saving via MCP Server")
        save_result = save_study_plan(
            filename=f"{args.user}_study_plan.json",
            content=final_responses["ScheduleBuilderAgent"],
        )
        if save_result["success"]:
            print(f"✅ Plan saved to: {save_result['path']}")
        else:
            print(f"❌ Save failed: {save_result['error']}")

    # ── Session state summary ──────────────────────────────────────────────────
    updated = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    if updated and updated.state:
        sep("💾 Session State Keys")
        for k, v in updated.state.items():
            preview = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
            print(f"  [{k}] {preview}")

    sep("✨ Done! Day 3 complete.")
    print("Next → Day 4: ContentAgent (summaries + MCQs per topic)")
    print("       Run `adk web .` to explore in the visual debugger")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StudyPlan AI — Day 3 runner")
    parser.add_argument("--pdf",   help="Path to PDF inside /data")
    parser.add_argument("--text",  help="Raw syllabus text")
    parser.add_argument("--days",  type=int,   help="Days until exam (default: 7)")
    parser.add_argument("--hours", type=float, help="Daily study hours (default: 4.0)")
    parser.add_argument("--user",  default="student_001", help="Student user ID")
    args = parser.parse_args()

    asyncio.run(main(args))