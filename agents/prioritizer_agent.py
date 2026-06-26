"""
agents/prioritizer_agent.py

PRIORITIZER AGENT
─────────────────
Responsibility: Read the structured topic list from session state and produce
a priority-ranked study order with reasoning.

ADK pattern used:
  - LlmAgent that reads {parsed_topics} from session.state (set by parser_agent)
  - output_key="priority_plan" writes its output for the next agent
  - The {key} template syntax in instruction is native ADK state injection
"""

from google.adk.agents import LlmAgent

MODEL = "gemini-2.5-flash"

PRIORITIZER_INSTRUCTION = """
You are an expert exam preparation strategist for engineering/university students.

You have received a structured JSON list of syllabus topics:

<syllabus_data>
{parsed_topics}
</syllabus_data>

Your job is to produce a PRIORITY-RANKED study plan.

Ranking criteria (apply ALL of them):
1. **Marks weightage** — topics with higher marks hint rank higher
2. **Foundational dependency** — prerequisite topics must be studied first
3. **Complexity** — high-complexity topics need more buffer days
4. **High-yield** — topics that appear frequently in exams rank higher

Output a single valid JSON object — no markdown, no explanation, just JSON.

Schema:
{
  "course_name": "<string>",
  "total_study_hours_estimate": <float>,
  "priority_ranked_topics": [
    {
      "rank": <int starting from 1>,
      "topic_id": "<e.g. U2T3>",
      "title": "<string>",
      "unit": "<unit title>",
      "priority_score": <int 1-10, 10=highest>,
      "priority_reason": "<1-sentence explanation>",
      "estimated_hours": <float>,
      "must_study_before": ["<topic_id>", ...],
      "difficulty": "<Easy | Medium | Hard>"
    }
  ],
  "quick_wins": ["<topic_id>", ...],
  "high_risk_topics": ["<topic_id>", ...]
}

Notes:
- quick_wins = high marks + low difficulty (study these first if short on time)
- high_risk_topics = hard + high marks (need the most focused time)
- must_study_before: list topic_ids that are prerequisites for this topic
- Output ONLY valid JSON. Do not add any text before or after.
"""


prioritizer_agent = LlmAgent(
    name="TopicPrioritizerAgent",
    model=MODEL,
    instruction=PRIORITIZER_INSTRUCTION,
    description=(
        "Reads the parsed syllabus topics and produces a priority-ranked "
        "study order based on marks weightage, difficulty, and dependencies."
    ),
    output_key="priority_plan",   # → session.state["priority_plan"]
)