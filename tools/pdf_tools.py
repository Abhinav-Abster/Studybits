"""
tools/pdf_tools.py

Agent Skills: reusable FunctionTools for reading syllabi.
ADK automatically wraps plain Python functions as FunctionTools —
the docstring IS the tool description the LLM reads to decide when to use it.
"""

import os
import re

# ── optional pdf dep ──────────────────────────────────────────────────────────
try:
    import pdfplumber
    _PDF_AVAILABLE = True
except ImportError:
    _PDF_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# SKILL 1 — read_pdf_file
# ─────────────────────────────────────────────────────────────────────────────

def read_pdf_file(file_path: str) -> dict:
    """
    Reads a PDF file from disk and returns its full text content.

    Use this tool when the user provides a path to a PDF syllabus file.
    Returns a dict with keys:
      - 'success': bool
      - 'text': extracted text (empty string on failure)
      - 'pages': number of pages extracted
      - 'error': error message if success is False
    """
    if not _PDF_AVAILABLE:
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": "pdfplumber not installed. Run: pip install pdfplumber",
        }

    # ── security: sanitize path ───────────────────────────────────────────────
    file_path = os.path.realpath(file_path)
    allowed_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    if not file_path.startswith(allowed_dir):
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"Access denied: file must be inside the /data directory.",
        }

    if not os.path.exists(file_path):
        return {"success": False, "text": "", "pages": 0, "error": f"File not found: {file_path}"}

    if not file_path.lower().endswith(".pdf"):
        return {"success": False, "text": "", "pages": 0, "error": "File must be a .pdf"}

    try:
        all_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
        combined = "\n\n".join(all_text)
        return {"success": True, "text": combined, "pages": len(all_text), "error": ""}
    except Exception as e:
        return {"success": False, "text": "", "pages": 0, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SKILL 2 — sanitize_syllabus_text
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_syllabus_text(raw_text: str) -> dict:
    """
    Cleans raw syllabus text before passing it to analysis agents.

    Removes excessive whitespace, special characters, and truncates to a safe
    length to prevent prompt injection and token overflows.

    Returns a dict with keys:
      - 'success': bool
      - 'clean_text': sanitized text string
      - 'original_length': character count before cleaning
      - 'clean_length': character count after cleaning
      - 'warning': non-fatal warning message (empty if none)
    """
    if not raw_text or not isinstance(raw_text, str):
        return {
            "success": False,
            "clean_text": "",
            "original_length": 0,
            "clean_length": 0,
            "warning": "Input must be a non-empty string.",
        }

    original_length = len(raw_text)
    warning = ""

    # Strip null bytes and control chars (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw_text)

    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)

    text = text.strip()

    # ── safety cap: ~12 000 tokens ≈ 48 000 chars ────────────────────────────
    MAX_CHARS = 48_000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        warning = f"Syllabus truncated to {MAX_CHARS} chars to stay within model limits."

    return {
        "success": True,
        "clean_text": text,
        "original_length": original_length,
        "clean_length": len(text),
        "warning": warning,
    }