"""
pipeline.py

THE PIPELINE (Day 3 version)
─────────────────────────────
SequentialAgent that runs:
  1. SyllabusParserAgent    → writes session.state["parsed_topics"]
  2. TopicPrioritizerAgent  → reads {parsed_topics}, writes session.state["priority_plan"]
  3. ScheduleBuilderAgent   → reads {priority_plan}, writes session.state["study_schedule"]

Day 4 will add ContentAgent to the sub_agents list here.

State flow:
  syllabus_text (user msg)
      ↓ ParserAgent         → parsed_topics
      ↓ PrioritizerAgent    → priority_plan
      ↓ ScheduleAgent       → study_schedule
"""

from google.adk.agents import SequentialAgent

from agents.parser_agent import parser_agent
from agents.prioritizer_agent import prioritizer_agent
from agents.schedule_agent import schedule_agent

root_agent = SequentialAgent(
    name="StudyPlanPipeline",
    description=(
        "Converts a syllabus into a prioritized, day-by-day study plan. "
        "Runs: Parser → Prioritizer → ScheduleBuilder in sequence."
    ),
    sub_agents=[
        parser_agent,
        prioritizer_agent,
        schedule_agent,
    ],
)