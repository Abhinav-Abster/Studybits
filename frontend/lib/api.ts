/**
 * lib/api.ts
 *
 * Type-safe API client for the StudyPlan AI backend.
 * Drop this into your Next.js project at lib/api.ts
 *
 * Usage:
 *   import { generatePlan, loadPlan } from "@/lib/api"
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
// Types — mirror the Python agent output schemas exactly
// ─────────────────────────────────────────────────────────────────────────────

export interface Topic {
  topic_id: string;
  title: string;
  subtopics: string[];
  marks_hint: string;
  estimated_hours: number;
}

export interface Unit {
  unit_number: number;
  unit_title: string;
  topics: Topic[];
}

export interface ParsedTopics {
  course_name: string;
  total_units: number;
  units: Unit[];
  exam_pattern_notes: string;
}

export interface RankedTopic {
  rank: number;
  topic_id: string;
  title: string;
  unit: string;
  priority_score: number;   // 1–10
  priority_reason: string;
  estimated_hours: number;
  must_study_before: string[];
  difficulty: "Easy" | "Medium" | "Hard";
}

export interface PriorityPlan {
  course_name: string;
  total_study_hours_estimate: number;
  priority_ranked_topics: RankedTopic[];
  quick_wins: string[];       // topic_ids
  high_risk_topics: string[]; // topic_ids
}

export interface ScheduledTopic {
  topic_id: string;
  title: string;
  hours: number;
  study_tip: string;
}

export interface ScheduleDay {
  day: number;
  label: string;
  daily_goal: string;
  topics: ScheduledTopic[];
  total_hours: number;
  is_revision_day: boolean;
}

export interface StudySchedule {
  course_name: string;
  total_days: number;
  daily_hours: number;
  schedule: ScheduleDay[];
  revision_days: number[];
  unscheduled_topics: string[];
  warnings: string[];
}

export interface MCQOption {
  A: string;
  B: string;
  C: string;
  D: string;
}

export interface MCQ {
  question: string;
  options: MCQOption;
  correct_answer: "A" | "B" | "C" | "D";
  explanation: string;
}

export interface ContentTopic {
  topic_id: string;
  title: string;
  unit: string;
  summary: string;        // markdown bullet string
  key_concepts: string[];
  mcqs: MCQ[];
}

export interface ContentPack {
  course_name: string;
  topics: ContentTopic[];
  total_topics: number;
  total_mcqs: number;
}

// ── SSE event payloads ────────────────────────────────────────────────────────

export interface ProgressEvent {
  agent: string;
  label: string;
  step: number;         // 1–4
  total_steps: number;  // always 4
}

export interface ResultEvent {
  agent: string;
  key: "parsed_topics" | "priority_plan" | "study_schedule" | "content_pack";
  data: ParsedTopics | PriorityPlan | StudySchedule | ContentPack;
}

export interface DoneEvent {
  saved: boolean;
  user_id: string;
  agent_count: number;
  agents_completed: string[];
}

export interface ErrorEvent {
  message: string;
}

// ── Collected pipeline output ─────────────────────────────────────────────────

export interface PlanResult {
  parsed_topics?: ParsedTopics;
  priority_plan?: PriorityPlan;
  study_schedule?: StudySchedule;
  content_pack?: ContentPack;
}

// ─────────────────────────────────────────────────────────────────────────────
// generatePlan — streams SSE events, calls your callbacks as each fires
// ─────────────────────────────────────────────────────────────────────────────

export interface GenerateOptions {
  syllabus: string;
  days: number;
  hours: number;
  userId: string;
  pdf?: File;

  onProgress?: (event: ProgressEvent) => void;
  onResult?: (event: ResultEvent) => void;
  onDone?: (event: DoneEvent, result: PlanResult) => void;
  onError?: (message: string) => void;
}

export async function generatePlan(opts: GenerateOptions): Promise<void> {
  const form = new FormData();
  form.append("syllabus", opts.syllabus);
  form.append("days",     String(opts.days));
  form.append("hours",    String(opts.hours));
  form.append("user_id",  opts.userId);
  if (opts.pdf) form.append("pdf", opts.pdf);

  const res = await fetch(`${API_BASE}/generate`, {
    method: "POST",
    body: form,
  });

  if (!res.ok || !res.body) {
    opts.onError?.(`HTTP ${res.status}: ${await res.text()}`);
    return;
  }

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  const result: PlanResult = {};

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";   // keep incomplete chunk

    for (const chunk of chunks) {
      if (!chunk.trim()) continue;

      // Parse SSE format: "event: <name>\ndata: <json>"
      const lines     = chunk.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event:"));
      const dataLine  = lines.find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const eventName = eventLine.replace("event:", "").trim();
      let   payload: unknown;
      try {
        payload = JSON.parse(dataLine.replace("data:", "").trim());
      } catch {
        continue;
      }

      switch (eventName) {
        case "progress":
          opts.onProgress?.(payload as ProgressEvent);
          break;

        case "result": {
          const r = payload as ResultEvent;
          // Store typed result
          (result as Record<string, unknown>)[r.key] = r.data;
          opts.onResult?.(r);
          break;
        }

        case "done":
          opts.onDone?.(payload as DoneEvent, result);
          break;

        case "error":
          opts.onError?.((payload as ErrorEvent).message);
          break;
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// loadPlan — fetch a saved plan by user ID
// ─────────────────────────────────────────────────────────────────────────────

export async function loadPlan(userId: string): Promise<StudySchedule | null> {
  const res = await fetch(`${API_BASE}/plan/${encodeURIComponent(userId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function loadParsedTopics(userId: string): Promise<ParsedTopics | null> {
  const res = await fetch(`${API_BASE}/parsed_topics/${encodeURIComponent(userId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function loadPriorityPlan(userId: string): Promise<PriorityPlan | null> {
  const res = await fetch(`${API_BASE}/priority_plan/${encodeURIComponent(userId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function loadContentPack(userId: string): Promise<ContentPack | null> {
  const res = await fetch(`${API_BASE}/content_pack/${encodeURIComponent(userId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function loadProfile(userId: string) {
  const res = await fetch(`${API_BASE}/profile/${encodeURIComponent(userId)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}