"""
pipeline.py  (root)

Root entry point for ADK tooling (adk web, adk run) and app.py / run.py.

The real agent tree lives in agents/:
  orchestrator_agent  ← root_agent (LlmAgent, routes by intent)
  ├── study_plan_pipeline  (SequentialAgent — full flow)
  │   ├── SyllabusParserAgent
  │   ├── TopicPrioritizerAgent
  │   ├── ScheduleBuilderAgent
  │   └── ContentGeneratorAgent
  └── StandaloneContentAgent  (direct MCQ/summary requests)

`adk web .` looks for `root_agent` in this file.
`app.py` and `run.py` also import `root_agent` from here.
"""

from agents.orchestrator_agent import orchestrator_agent

root_agent = orchestrator_agent