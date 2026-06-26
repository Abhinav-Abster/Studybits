"""
agents/parser_agent.py

PARSER AGENT
────────────
Responsibility: Take raw (cleaned) syllabus text and output a structured JSON
list of topics with metadata.

ADK pattern used:
  - LlmAgent with output_key="parsed_topics"
  - output_key writes the agent's final response into session.state
    so the next agent in the SequentialAgent can read it as {parsed_topics}
"""

from google.adk.agents import LlmAgent

MODEL = "gemini-2.5-flash"

PARSER_INSTRUCTION = """
You are an expert academic syllabus analyst.

You will receive the full text of a course syllabus.
Your ONLY job is to extract ALL topics and subtopics from it.

Output a single valid JSON object — no markdown fences, no explanation, just JSON.

Schema:
{
  "course_name": "<string>",
  "total_units": <int>,
  "units": [
    {
      "unit_number": <int>,
      "unit_title": "<string>",
      "topics": [
        {
          "topic_id": "<e.g. U1T1>",
          "title": "<string>",
          "subtopics": ["<string>", ...],
          "marks_hint": "<e.g. '16 marks' or 'unknown'>",
          "estimated_hours": <float>
        }
      ]
    }
  ],
  "exam_pattern_notes": "<any notes about exam structure, marks distribution, etc.>"
}

Rules:
1. Extract EVERY topic you find, even if mentioned briefly.
2. If marks distribution is mentioned, capture it in marks_hint.
3. Estimate hours honestly — a complex topic = 2-4 hrs, simple = 0.5-1 hr.
4. If the course name is not explicit, infer it from context.
5. Output ONLY valid JSON. Do not add any text before or after.
"""


parser_agent = LlmAgent(
    name="SyllabusParserAgent",
    model=MODEL,
    instruction=PARSER_INSTRUCTION,
    description=(
        "Parses raw syllabus text and extracts a structured JSON list of "
        "all units, topics, subtopics, and marks hints."
    ),
    output_key="parsed_topics",   # saves output → session.state["parsed_topics"]
)