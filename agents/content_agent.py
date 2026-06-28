"""
agents/content_agent.py

CONTENT AGENT
─────────────
Responsibility: Read the study schedule from session state and generate
concise summaries + multiple-choice questions for every topic.

ADK pattern:
  - Reads {study_schedule} and {parsed_topics} from session.state
    (set by ScheduleBuilderAgent and SyllabusParserAgent respectively)
  - output_key="content_pack" → session.state["content_pack"]
  - Produces study notes + 3-5 MCQs per topic with explanations
"""

from google.adk.agents import LlmAgent
from google.genai import types as genai_types
from agents.config import MODEL

CONTENT_INSTRUCTION = """
You are an expert academic content creator and exam coach for university students.

You have the structured study schedule and parsed topics:

<study_schedule>
{study_schedule}
</study_schedule>

<parsed_topics>
{parsed_topics}
</parsed_topics>

Your job is to create a COMPLETE content pack with summaries and MCQs for EVERY topic.

For each topic, generate:
1. **Summary** — concise, bullet-point study notes covering all key concepts.
   Keep it practical: definitions, formulas, key steps, common pitfalls.
   Use markdown formatting for clarity.
2. **Key Concepts** — a flat list of the most important terms/ideas to remember.
3. **MCQs** — 3 to 5 multiple-choice questions that test real understanding,
   not just rote recall. Include tricky distractors. Each MCQ must have
   exactly 4 options (A, B, C, D), one correct answer, and a brief explanation.

Output a single valid JSON object — no markdown fences, no explanation, just JSON.

Schema:
{
  "course_name": "<string>",
  "topics": [
    {
      "topic_id": "<e.g. U1T1>",
      "title": "<string>",
      "unit": "<unit title>",
      "summary": "<markdown bullet-point summary>",
      "key_concepts": ["<string>", ...],
      "mcqs": [
        {
          "question": "<string>",
          "options": {
            "A": "<string>",
            "B": "<string>",
            "C": "<string>",
            "D": "<string>"
          },
          "correct_answer": "<A|B|C|D>",
          "explanation": "<1-2 sentence explanation of why the answer is correct>"
        }
      ]
    }
  ],
  "total_topics": <int>,
  "total_mcqs": <int>
}

Rules:
1. Cover EVERY topic from the schedule — do not skip any.
2. Summaries should be 4-8 bullet points, each 1-2 sentences.
3. MCQs should test understanding, not just definitions.
4. At least one MCQ per topic should be application-based.
5. Difficulty mix: 1 Easy, 1-2 Medium, 1 Hard per topic.
6. Output ONLY valid JSON. Do not add any text before or after.
"""

content_agent = LlmAgent(
    name="ContentGeneratorAgent",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION,
    description=(
        "Reads the study schedule and parsed topics, then generates concise "
        "summaries and 3-5 MCQs with answer keys for every topic."
    ),
    output_key="content_pack",
    generate_content_config=genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        max_output_tokens=65536,
    ),
)