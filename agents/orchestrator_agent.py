"""
agents/orchestrator_agent.py

ORCHESTRATOR AGENT
──────────────────
Responsibility: Act as the intelligent front-door for StudyPlan AI.
Routes user requests to the correct sub-agent based on intent.

ADK pattern:
  - LlmAgent with sub_agents=[...] — uses ADK's built-in agent-transfer
    mechanism where the LLM decides which sub-agent to delegate to
  - Sub-agents:
      1. StudyPlanPipeline (SequentialAgent) — full syllabus → plan flow
      2. StandaloneContentAgent — summaries/MCQ generation from existing topics

The Orchestrator's instruction describes each sub-agent's capability so
Gemini can route based on the user's natural language intent.
"""

from google.adk.agents import LlmAgent
from google.genai import types as genai_types

from agents.config import MODEL
from agents.content_agent import CONTENT_INSTRUCTION
from agents.pipeline import study_plan_pipeline

# ── Standalone content agent ───────────────────────────────────────────────────
# ADK requires each agent instance to have exactly one parent.
# The pipeline already owns its ContentGeneratorAgent instance,
# so we create a separate one here for direct orchestrator routing.
standalone_content_agent = LlmAgent(
    name="StandaloneContentAgent",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION,
    description=(
        "Standalone content generator: reads parsed topics from session state "
        "and generates summaries + MCQs. Use when the user already has topics "
        "from a previous pipeline run and wants to regenerate content."
    ),
    output_key="content_pack",
    generate_content_config=genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        max_output_tokens=65536,
    ),
)

ORCHESTRATOR_INSTRUCTION = """
You are the StudyPlan AI orchestrator. You help university students prepare for exams.

You have access to specialized sub-agents. Based on the user's request, delegate
to the most appropriate one. Here is what each can do:

1. **StudyPlanPipeline** — Use this when the user provides a syllabus (text or
   mentions topics/units) and wants a full study plan. This pipeline will:
   - Parse the syllabus into structured topics
   - Prioritize topics by marks, difficulty, and dependencies
   - Build a day-by-day study schedule
   - Generate summaries and MCQs for each topic

2. **StandaloneContentAgent** — Use this when the user already has topics in
   session state (from a previous pipeline run) and wants to generate or
   regenerate summaries and MCQs. For example:
   - "Generate MCQs for my topics"
   - "Give me study notes"
   - "Create practice questions"

Decision rules:
- If the user provides syllabus text or a course description → delegate to StudyPlanPipeline
- If the user asks for summaries, notes, or MCQs and session already has parsed topics → delegate to StandaloneContentAgent
- If the request is ambiguous, ask the user a brief clarifying question
- NEVER try to do the work yourself — always delegate to a sub-agent

When greeting the user or when no specific task is requested, briefly introduce
yourself and list what you can help with.
"""

orchestrator_agent = LlmAgent(
    name="StudyPlanOrchestrator",
    model=MODEL,
    instruction=ORCHESTRATOR_INSTRUCTION,
    description=(
        "Intelligent router that directs user requests to the appropriate "
        "sub-agent: full study plan pipeline or standalone content generation."
    ),
    sub_agents=[
        study_plan_pipeline,
        standalone_content_agent,
    ],
)