"""
agents/schedule_agent.py

SCHEDULE AGENT
──────────────
Responsibility: Read the priority-ranked plan from session state and build a
realistic day-by-day study calendar.

ADK pattern:
  - Reads {priority_plan} injected from session.state (set by prioritizer_agent)
  - output_key="study_schedule" → session.state["study_schedule"] for Day 4 agents
  - days_until_exam and daily_hours come from session.state too (set in run.py)
"""

from google.adk.agents import LlmAgent
from google.genai import types as genai_types
from agents.config import MODEL

SCHEDULE_INSTRUCTION = """
You are an expert study schedule builder for university students preparing for exams.

You have the following priority-ranked topic plan:
<priority_plan>
{priority_plan}
</priority_plan>

Student context:
- Days until exam: {days_until_exam}
- Daily study hours available: {daily_hours}

Build a realistic day-by-day study schedule following these rules:
1. Respect topic dependencies — topics in must_study_before must appear in earlier days
2. Fit topics within the daily hours budget (do NOT exceed daily_hours per day)
3. High priority_score topics get scheduled FIRST (earlier days)
4. Reserve the LAST 2 days purely for full revision — no new topics
5. If topics don't fit in the available days, note it as a warning
6. Each day should have a clear daily_goal summary sentence
7. quick_wins topics can be batched together on one day

Output a single valid JSON object — no markdown fences, no explanation, just JSON.

Schema:
{
  "course_name": "<string>",
  "total_days": <int>,
  "daily_hours": <float>,
  "schedule": [
    {
      "day": <int>,
      "label": "<e.g. 'Day 1 — Foundation'>",
      "daily_goal": "<one sentence describing the day's focus>",
      "topics": [
        {
          "topic_id": "<string>",
          "title": "<string>",
          "hours": <float>,
          "study_tip": "<one practical tip for this topic>"
        }
      ],
      "total_hours": <float>,
      "is_revision_day": <bool>
    }
  ],
  "revision_days": [<day numbers>],
  "unscheduled_topics": ["<topic_id if couldn't fit>"],
  "warnings": ["<any scheduling conflicts or concerns>"]
}

Output ONLY valid JSON. Do not add any text before or after.
"""

schedule_agent = LlmAgent(
    name="ScheduleBuilderAgent",
    model=MODEL,
    instruction=SCHEDULE_INSTRUCTION,
    description=(
        "Reads the priority-ranked topic plan and builds a day-by-day study "
        "calendar that respects topic dependencies and daily hour budgets."
    ),
    output_key="study_schedule",  # → session.state["study_schedule"]
    generate_content_config=genai_types.GenerateContentConfig(
        response_mime_type="application/json",
    ),
)