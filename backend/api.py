"""
backend/api.py

FastAPI backend for StudyPlan AI.
Replaces Gradio — Next.js frontend talks to these endpoints.

Run:
    cd studyplan_agents
    uvicorn backend.api:app --reload --port 8000

Endpoints:
    POST /generate          → SSE stream of agent progress + final results
    GET  /plan/{user_id}    → load a saved plan from MCP server
    GET  /health            → sanity check
"""

import asyncio
import json
import os
import re
import sys
import uuid
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ── ADK imports ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from pipeline import root_agent
from tools.pdf_tools import read_pdf_file, sanitize_syllabus_text
from mcp_server.server import (
    save_study_plan, load_study_plan, list_saved_plans,
    save_user_profile, load_user_profile,
    save_content_pack, load_content_pack,
)

# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="StudyPlan AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://studybits-woad.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_NAME = "studyplan_ai"

# ── Agent display names for the frontend progress UI ──────────────────────────
AGENT_META = {
    "StudyPlanOrchestrator":  {"label": "Orchestrator",  "step": 0},
    "SyllabusParserAgent":    {"label": "Parsing syllabus",    "step": 1},
    "TopicPrioritizerAgent":  {"label": "Ranking topics",      "step": 2},
    "ScheduleBuilderAgent":   {"label": "Building schedule",   "step": 3},
    "ContentGeneratorAgent":  {"label": "Generating study pack", "step": 4},
    "StandaloneContentAgent": {"label": "Generating content",  "step": 4},
}


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


def sse_event(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline runner (async generator — streams events)
# ─────────────────────────────────────────────────────────────────────────────

async def stream_pipeline(
    syllabus_text: str,
    days: int,
    hours: float,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Runs the ADK pipeline and yields SSE events:

      event: progress   — { agent, label, step, total_steps: 4 }
      event: result     — { agent, key, data }   (one per agent that finishes)
      event: done       — { saved, user_id, agent_count }
      event: error      — { message }
    """
    session_service = InMemorySessionService()
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
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

    # Map agent name → which session state key holds its output
    OUTPUT_KEYS = {
        "SyllabusParserAgent":    "parsed_topics",
        "TopicPrioritizerAgent":  "priority_plan",
        "ScheduleBuilderAgent":   "study_schedule",
        "ContentGeneratorAgent":  "content_pack",
        "StandaloneContentAgent": "content_pack",
    }

    responses = {}
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if not (event.author and event.content):
                continue

            parts = [p.text for p in event.content.parts if hasattr(p, "text") and p.text]
            text = "".join(parts).strip()
            if not text:
                continue

            author = event.author
            responses[author] = text
            meta = AGENT_META.get(author, {"label": author, "step": 0})

            import logging
            logging.getLogger("studyplan").info(
                f"Event from author={author} text_len={len(text)} in_output_keys={author in OUTPUT_KEYS}"
            )

            # Yield progress event
            yield sse_event("progress", {
                "agent": author,
                "label": meta["label"],
                "step": meta["step"],
                "total_steps": 4,
            })

            clean_text = extract_json_substring(text)

            try:
                parsed = json.loads(clean_text)
                result_data = parsed
            except Exception as parse_err:
                result_data = text
                import logging
                logging.getLogger("studyplan").warning(
                    f"JSON parse failed for {author}: {parse_err!r} — first 200 chars: {text[:200]}"
                )

            # Yield result event (only for pipeline sub-agents, not orchestrator)
            if author in OUTPUT_KEYS:
                is_dict = isinstance(result_data, dict)
                import logging
                logging.getLogger("studyplan").info(
                    f"Yielding result for {author} key={OUTPUT_KEYS[author]} is_dict={is_dict}"
                )
                yield sse_event("result", {
                    "agent": author,
                    "key": OUTPUT_KEYS[author],
                    "data": result_data,
                })

    except Exception as e:
        yield sse_event("error", {"message": str(e)})
        return

    # ── Save via MCP ──────────────────────────────────────────────────────────
    saved = False
    if "SyllabusParserAgent" in responses:
        clean_parser_json = extract_json_substring(responses["SyllabusParserAgent"])
        save_study_plan(f"{user_id}_parsed_topics.json", clean_parser_json)

    if "TopicPrioritizerAgent" in responses:
        clean_prioritizer_json = extract_json_substring(responses["TopicPrioritizerAgent"])
        save_study_plan(f"{user_id}_priority_plan.json", clean_prioritizer_json)

    if "ScheduleBuilderAgent" in responses:
        clean_schedule_json = extract_json_substring(responses["ScheduleBuilderAgent"])
        r = save_study_plan(f"{user_id}_plan.json", clean_schedule_json)
        saved = r.get("success", False)

    if "ContentGeneratorAgent" in responses:
        clean_content_json = extract_json_substring(responses["ContentGeneratorAgent"])
        save_content_pack(f"{user_id}_content.json", clean_content_json)

    save_user_profile(user_id, json.dumps({
        "user_id": user_id,
        "days_until_exam": days,
        "daily_hours": hours,
    }))

    yield sse_event("done", {
        "saved": saved,
        "user_id": user_id,
        "agent_count": len(responses),
        "agents_completed": list(responses.keys()),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": root_agent.name}


@app.post("/generate")
async def generate(
    syllabus: str       = Form(...),
    days: int           = Form(7),
    hours: float        = Form(4.0),
    user_id: str        = Form("student_001"),
    pdf: UploadFile     = File(None),
):
    """
    Start the pipeline. Returns an SSE stream.

    Send as multipart/form-data:
      syllabus  — raw syllabus text (string)
      days      — days until exam (int, default 7)
      hours     — daily study hours (float, default 4.0)
      user_id   — student identifier (string)
      pdf       — optional PDF file (overrides syllabus text)

    SSE event types:
      progress  { agent, label, step, total_steps }
      result    { agent, key, data }
      done      { saved, user_id, agent_count, agents_completed }
      error     { message }
    """
    # ── Security: sanitize user_id ────────────────────────────────────────────
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id.strip())[:64] or "student_001"

    # ── Clamp numeric inputs ──────────────────────────────────────────────────
    days  = max(1, min(60, days))
    hours = max(0.5, min(12.0, hours))

    # ── PDF overrides text ────────────────────────────────────────────────────
    if pdf is not None:
        raw_bytes = await pdf.read()
        tmp_path  = f"/tmp/syllabus_{uuid.uuid4().hex[:8]}.pdf"
        with open(tmp_path, "wb") as f:
            f.write(raw_bytes)
        result = read_pdf_file(tmp_path)
        os.unlink(tmp_path)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=f"PDF error: {result['error']}")
        raw_text = result["text"]
    else:
        raw_text = syllabus

    # ── Sanitize ──────────────────────────────────────────────────────────────
    clean = sanitize_syllabus_text(raw_text)
    if not clean["success"] or not clean["clean_text"].strip():
        raise HTTPException(status_code=400, detail="No readable syllabus text found.")

    return StreamingResponse(
        stream_pipeline(clean["clean_text"], days, hours, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # disables nginx buffering
        },
    )


@app.get("/plan/{user_id}")
def get_plan(user_id: str):
    """Load a previously saved study plan for a user."""
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
    result  = load_study_plan(f"{user_id}_plan.json")
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    try:
        return JSONResponse(content=json.loads(result["content"]))
    except Exception:
        return JSONResponse(content={"raw": result["content"]})


@app.get("/plans")
def get_all_plans():
    """List all saved plans."""
    return list_saved_plans()


@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    """Load a student's saved profile."""
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
    return load_user_profile(user_id)


@app.get("/parsed_topics/{user_id}")
def get_parsed_topics(user_id: str):
    """Load a saved parsed topics list."""
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
    result = load_study_plan(f"{user_id}_parsed_topics.json")
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    try:
        return JSONResponse(content=json.loads(result["content"]))
    except Exception:
        return JSONResponse(content={"raw": result["content"]})


@app.get("/priority_plan/{user_id}")
def get_priority_plan(user_id: str):
    """Load a saved priority roadmap."""
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
    result = load_study_plan(f"{user_id}_priority_plan.json")
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    try:
        return JSONResponse(content=json.loads(result["content"]))
    except Exception:
        return JSONResponse(content={"raw": result["content"]})


@app.get("/content_pack/{user_id}")
def get_content_pack(user_id: str):
    """Load a saved study content pack."""
    user_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
    result = load_content_pack(f"{user_id}_content.json")
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    try:
        return JSONResponse(content=json.loads(result["content"]))
    except Exception:
        return JSONResponse(content={"raw": result["content"]})