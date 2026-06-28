"""
agents/pipeline.py

SEQUENTIAL PIPELINE
────────────────────
Exported as `study_plan_pipeline` — used by orchestrator_agent as a sub-agent.

Flow:
  SyllabusParserAgent      → session.state["parsed_topics"]
  TopicPrioritizerAgent    → session.state["priority_plan"]
  ScheduleBuilderAgent     → session.state["study_schedule"]
  ContentGeneratorAgent    → session.state["content_pack"]
"""

import warnings
warnings.filterwarnings("ignore", message=".*SequentialAgent is deprecated.*")

from google.adk.agents import SequentialAgent

from agents.parser_agent import parser_agent
from agents.prioritizer_agent import prioritizer_agent
from agents.schedule_agent import schedule_agent
from agents.content_agent import content_agent

study_plan_pipeline = SequentialAgent(
    name="StudyPlanPipeline",
    description=(
        "Full syllabus-to-study-plan pipeline. Give it a syllabus and it runs: "
        "Parser → Prioritizer → ScheduleBuilder → ContentGenerator in sequence."
    ),
    sub_agents=[
        parser_agent,
        prioritizer_agent,
        schedule_agent,
        content_agent,
    ],
)