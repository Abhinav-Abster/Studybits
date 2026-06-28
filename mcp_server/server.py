"""
mcp_server/server.py

STUDYPLAN MCP SERVER
─────────────────────
A local MCP server that exposes file I/O tools to the ADK agents.
Agents call these tools via MCPToolset instead of touching the filesystem directly.

Tools exposed:
  - save_study_plan(filename, content)   → writes JSON plan to /data
  - load_study_plan(filename)            → reads a saved plan back
  - load_user_profile(user_id)           → loads student exam context
  - save_user_profile(user_id, profile)  → persists student preferences
  - list_saved_plans()                   → lists all saved plans

Competition requirement: MCP Server ✅

Run standalone for testing:
    python mcp_server/server.py

Agents connect to it via:
    MCPToolset(connection_params=StdioServerParameters(
        command="python", args=["mcp_server/server.py"]
    ))
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ── Server setup ───────────────────────────────────────────────────────────────
mcp = FastMCP(
    name="StudyPlanServer",
    instructions=(
        "File I/O server for StudyPlan AI. "
        "Use save_study_plan to persist generated plans, "
        "load_study_plan to retrieve them, and "
        "load_user_profile / save_user_profile to manage student context."
    ),
)

# ── Data directory (all files sandboxed here) ──────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

PLANS_DIR = DATA_DIR / "plans"
PLANS_DIR.mkdir(exist_ok=True)

PROFILES_DIR = DATA_DIR / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

CONTENT_DIR = DATA_DIR / "content"
CONTENT_DIR.mkdir(exist_ok=True)


# ── Security helper ────────────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """Strips path traversal attempts and non-alphanumeric chars."""
    name = os.path.basename(name)                    # strip any directory part
    name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)  # allow only safe chars
    name = re.sub(r"\.{2,}", ".", name)              # no double-dots
    return name[:128]                                 # cap length


def _safe_path(directory: Path, filename: str) -> Path:
    """Returns a resolved path guaranteed to be inside directory."""
    safe = _safe_filename(filename)
    resolved = (directory / safe).resolve()
    if not str(resolved).startswith(str(directory.resolve())):
        raise ValueError(f"Path traversal attempt blocked: {filename}")
    return resolved


# ── MCP Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def save_study_plan(filename: str, content: str) -> dict:
    """
    Save a generated study plan to disk as a JSON file.

    Args:
        filename: Name for the file (e.g. 'daa_plan.json'). Must be alphanumeric.
        content:  The study plan content as a JSON string or plain text.

    Returns:
        dict with 'success', 'path', and optional 'error'.
    """
    try:
        if not filename.endswith(".json"):
            filename += ".json"
        path = _safe_path(PLANS_DIR, filename)

        # Try to pretty-print if valid JSON, else save as-is
        try:
            parsed = json.loads(content)
            to_write = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            to_write = content

        path.write_text(to_write, encoding="utf-8")
        return {"success": True, "path": str(path), "error": ""}
    except Exception as e:
        return {"success": False, "path": "", "error": str(e)}


@mcp.tool()
def load_study_plan(filename: str) -> dict:
    """
    Load a previously saved study plan from disk.

    Args:
        filename: Name of the file to load (e.g. 'daa_plan.json').

    Returns:
        dict with 'success', 'content' (string), 'filename', and optional 'error'.
    """
    try:
        if not filename.endswith(".json"):
            filename += ".json"
        path = _safe_path(PLANS_DIR, filename)

        if not path.exists():
            return {
                "success": False,
                "content": "",
                "filename": filename,
                "error": f"File not found: {filename}",
            }

        content = path.read_text(encoding="utf-8")
        return {"success": True, "content": content, "filename": filename, "error": ""}
    except Exception as e:
        return {"success": False, "content": "", "filename": filename, "error": str(e)}


@mcp.tool()
def list_saved_plans() -> dict:
    """
    List all study plans saved to disk.

    Returns:
        dict with 'success', 'plans' (list of filenames), and 'count'.
    """
    try:
        files = sorted(PLANS_DIR.glob("*.json"))
        names = [f.name for f in files]
        return {"success": True, "plans": names, "count": len(names)}
    except Exception as e:
        return {"success": False, "plans": [], "count": 0, "error": str(e)}


@mcp.tool()
def save_user_profile(user_id: str, profile: str) -> dict:
    """
    Save a student's exam context profile (days until exam, daily hours, course, etc.).

    Args:
        user_id: Unique student identifier (e.g. 'student_001').
        profile: JSON string with keys: days_until_exam, daily_hours, course_name, notes.

    Returns:
        dict with 'success', 'path', and optional 'error'.
    """
    try:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
        filename = f"{safe_id}.json"
        path = _safe_path(PROFILES_DIR, filename)

        try:
            parsed = json.loads(profile)
            parsed["last_updated"] = datetime.utcnow().isoformat()
            to_write = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            to_write = profile

        path.write_text(to_write, encoding="utf-8")
        return {"success": True, "path": str(path), "error": ""}
    except Exception as e:
        return {"success": False, "path": "", "error": str(e)}


@mcp.tool()
def load_user_profile(user_id: str) -> dict:
    """
    Load a student's saved exam context profile.

    Args:
        user_id: Unique student identifier (e.g. 'student_001').

    Returns:
        dict with 'success', 'profile' (dict), and optional 'error'.
        If no profile exists, returns a sensible default profile.
    """
    try:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id)[:64]
        filename = f"{safe_id}.json"
        path = _safe_path(PROFILES_DIR, filename)

        if not path.exists():
            # Return a default profile rather than an error
            default = {
                "user_id": user_id,
                "days_until_exam": 7,
                "daily_hours": 4.0,
                "course_name": "Unknown Course",
                "notes": "No profile saved yet — using defaults.",
            }
            return {"success": True, "profile": default, "error": ""}

        raw = path.read_text(encoding="utf-8")
        profile = json.loads(raw)
        return {"success": True, "profile": profile, "error": ""}
    except Exception as e:
        return {"success": False, "profile": {}, "error": str(e)}


# ── Content Pack Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def save_content_pack(filename: str, content: str) -> dict:
    """
    Save a generated content pack (summaries + MCQs) to disk as a JSON file.

    Args:
        filename: Name for the file (e.g. 'daa_content.json'). Must be alphanumeric.
        content:  The content pack as a JSON string.

    Returns:
        dict with 'success', 'path', and optional 'error'.
    """
    try:
        if not filename.endswith(".json"):
            filename += ".json"
        path = _safe_path(CONTENT_DIR, filename)

        # Try to pretty-print if valid JSON, else save as-is
        try:
            parsed = json.loads(content)
            to_write = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            to_write = content

        path.write_text(to_write, encoding="utf-8")
        return {"success": True, "path": str(path), "error": ""}
    except Exception as e:
        return {"success": False, "path": "", "error": str(e)}


@mcp.tool()
def load_content_pack(filename: str) -> dict:
    """
    Load a previously saved content pack from disk.

    Args:
        filename: Name of the file to load (e.g. 'daa_content.json').

    Returns:
        dict with 'success', 'content' (string), 'filename', and optional 'error'.
    """
    try:
        if not filename.endswith(".json"):
            filename += ".json"
        path = _safe_path(CONTENT_DIR, filename)

        if not path.exists():
            return {
                "success": False,
                "content": "",
                "filename": filename,
                "error": f"File not found: {filename}",
            }

        content = path.read_text(encoding="utf-8")
        return {"success": True, "content": content, "filename": filename, "error": ""}
    except Exception as e:
        return {"success": False, "content": "", "filename": filename, "error": str(e)}


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 StudyPlan MCP Server starting (stdio transport)...")
    print(f"   Data directory: {DATA_DIR}")
    print(f"   Plans dir:      {PLANS_DIR}")
    print(f"   Profiles dir:   {PROFILES_DIR}")
    print(f"   Content dir:    {CONTENT_DIR}")
    print("   Tools: save_study_plan, load_study_plan, list_saved_plans,")
    print("          save_user_profile, load_user_profile,")
    print("          save_content_pack, load_content_pack")
    mcp.run(transport="stdio")