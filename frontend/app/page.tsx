"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  BookOpen,
  Zap,
  CloudUpload,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Loader2,
  BookMarked,
  Lightbulb,
  X,
  Upload,
  Hash,
  Clock,
  Star,
  Target,
  Calendar,
  Brain,
  FileText,
  ArrowRight,
} from "lucide-react";
import {
  generatePlan,
  loadPlan,
  loadProfile,
  loadParsedTopics,
  loadPriorityPlan,
  loadContentPack,
  healthCheck,
  type ParsedTopics,
  type PriorityPlan,
  type StudySchedule,
  type ContentPack,
  type PlanResult,
  type ProgressEvent,
  type ResultEvent,
} from "@/lib/api";

const SAMPLE_SYLLABUS = `Course: Design and Analysis of Algorithms (21CSC204J)
Credit: 4  |  Exam: 100 marks (Part A: 20 MCQ x 1 = 20, Part B: 5 x 16 = 80)

UNIT I — Introduction to Algorithms (16 marks)
  - Divide and Conquer: Merge Sort, Quick Sort, Binary Search
  - Recurrence relations: Master Theorem, Substitution method
  - Time & Space complexity: Big-O, Theta, Omega

UNIT II — Greedy Algorithms (16 marks)
  - Activity Selection, Huffman Coding, Fractional Knapsack
  - Minimum Spanning Tree: Prim's, Kruskal's
  - Dijkstra's Shortest Path

UNIT III — Dynamic Programming (16 marks)
  - Matrix Chain Multiplication, 0/1 Knapsack, LCS
  - Bellman-Ford, Floyd-Warshall

UNIT IV — Backtracking and Branch & Bound (16 marks)
  - N-Queens, Graph Coloring, Hamiltonian Cycle
  - TSP via Branch and Bound

UNIT V — NP-Completeness (16 marks)
  - P, NP, NP-Hard, NP-Complete, Cook's Theorem
  - Approximation and Randomized Algorithms`;

const AGENT_STEPS = [
  {
    id: "SyllabusParserAgent",
    label: "Parse Syllabus",
    step: 1,
    desc: "Structuring course topics & units",
  },
  {
    id: "TopicPrioritizerAgent",
    label: "Rank Priority",
    step: 2,
    desc: "Scoring topics by difficulty & weight",
  },
  {
    id: "ScheduleBuilderAgent",
    label: "Build Schedule",
    step: 3,
    desc: "Creating day-by-day study roadmap",
  },
  {
    id: "ContentGeneratorAgent",
    label: "Generate Study Pack",
    step: 4,
    desc: "Writing notes, key concepts & MCQs",
  },
];

/* Wobbly radius presets for inline style diversity */
const WOBBLY_PRESETS = [
  "255px 15px 225px 15px / 15px 225px 15px 255px",
  "15px 225px 15px 255px / 255px 15px 225px 15px",
  "185px 25px 195px 20px / 20px 195px 25px 185px",
  "105px 10px 120px 10px / 10px 120px 10px 105px",
  "225px 20px 205px 25px / 25px 205px 20px 225px",
];

function wobbly(index: number) {
  return { borderRadius: WOBBLY_PRESETS[index % WOBBLY_PRESETS.length] };
}

export default function Home() {
  // Inputs
  const [syllabus, setSyllabus] = useState(SAMPLE_SYLLABUS);
  const [days, setDays] = useState(7);
  const [hours, setHours] = useState(4.0);
  const [userId, setUserId] = useState("student_001");
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  // Status & Progress
  const [backendAlive, setBackendAlive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Output Results
  const [parsedTopics, setParsedTopics] = useState<ParsedTopics | null>(null);
  const [priorityPlan, setPriorityPlan] = useState<PriorityPlan | null>(null);
  const [studySchedule, setStudySchedule] = useState<StudySchedule | null>(
    null
  );
  const [contentPack, setContentPack] = useState<ContentPack | null>(null);

  // Navigation
  const [activeTab, setActiveTab] = useState<
    "topics" | "priority" | "schedule" | "content"
  >("topics");

  // Interaction State
  const [expandedUnits, setExpandedUnits] = useState<Record<number, boolean>>(
    {}
  );
  const [completedDays, setCompletedDays] = useState<Record<number, boolean>>(
    {}
  );
  const [selectedAnswers, setSelectedAnswers] = useState<
    Record<string, "A" | "B" | "C" | "D">
  >({});
  const [quizScore, setQuizScore] = useState({ correct: 0, total: 0 });

  const logContainerRef = useRef<HTMLDivElement>(null);

  // Check health on mount and poll periodically to handle wake-ups (e.g. cold starts)
  useEffect(() => {
    let active = true;
    const check = async () => {
      const alive = await healthCheck();
      if (active) setBackendAlive(alive);
    };
    check();
    const interval = setInterval(check, 15000); // Check every 15s
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Scroll logs to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [progressLog]);

  // Load Saved Profile / Plan
  const handleLoadSaved = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const profile = await loadProfile(userId);
      setBackendAlive(true);
      if (profile && profile.success && profile.profile) {
        const p = JSON.parse(profile.profile);
        if (p.days_until_exam) setDays(Number(p.days_until_exam));
        if (p.daily_hours) setHours(Number(p.daily_hours));
      }

      const [savedPlan, savedTopics, savedPriority, savedContent] =
        await Promise.all([
          loadPlan(userId),
          loadParsedTopics(userId),
          loadPriorityPlan(userId),
          loadContentPack(userId),
        ]);

      if (savedPlan) {
        setStudySchedule(savedPlan);
        if (savedTopics) setParsedTopics(savedTopics);
        if (savedPriority) setPriorityPlan(savedPriority);
        if (savedContent) setContentPack(savedContent);
        setSuccessMsg(
          `Successfully loaded study plan and data for user "${userId}"!`
        );
        setActiveTab("topics");
      } else {
        setErrorMsg(`No saved plan found for Student ID "${userId}".`);
      }
    } catch (e: any) {
      setErrorMsg(`Failed to load saved data: ${e.message || e}`);
    }
  };

  // Run Generation
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setProgressLog(["Initiating 4-Agent Pipeline..."]);
    setCurrentAgent("SyllabusParserAgent");
    setCurrentStep(1);

    // Clear previous results
    setParsedTopics(null);
    setPriorityPlan(null);
    setStudySchedule(null);
    setContentPack(null);
    setSelectedAnswers({});
    setQuizScore({ correct: 0, total: 0 });

    try {
      await generatePlan({
        syllabus,
        days,
        hours,
        userId,
        pdf: pdfFile || undefined,
        onProgress: (p: ProgressEvent) => {
          setBackendAlive(true);
          setCurrentAgent(p.agent);
          setCurrentStep(p.step);
          setProgressLog((prev) => [
            ...prev,
            `⏳ [${p.label}] Step ${p.step}/${p.total_steps} in progress...`,
          ]);
        },
        onResult: (r: ResultEvent) => {
          setBackendAlive(true);
          console.log("[SSE Result]", r.key, r.agent, typeof r.data, r.data);
          setProgressLog((prev) => [
            ...prev,
            `✅ [${r.agent}] Completed successfully!`,
          ]);
          if (r.key === "parsed_topics") {
            setParsedTopics(r.data as ParsedTopics);
          } else if (r.key === "priority_plan") {
            setPriorityPlan(r.data as PriorityPlan);
          } else if (r.key === "study_schedule") {
            console.log(
              "[SSE] study_schedule data:",
              JSON.stringify(r.data).slice(0, 500)
            );
            setStudySchedule(r.data as StudySchedule);
          } else if (r.key === "content_pack") {
            console.log(
              "[SSE] content_pack data:",
              JSON.stringify(r.data).slice(0, 500)
            );
            setContentPack(r.data as ContentPack);
          }
        },
        onDone: (doneEvent) => {
          setBackendAlive(true);
          setIsLoading(false);
          setCurrentAgent(null);
          setCurrentStep(0);
          setProgressLog((prev) => [
            ...prev,
            `🎉 Study Plan successfully built and saved for student "${doneEvent.user_id}"!`,
          ]);
          setSuccessMsg(`Study Plan successfully generated!`);
        },
        onError: (err) => {
          setIsLoading(false);
          setCurrentAgent(null);
          setCurrentStep(0);
          setErrorMsg(err);
          setProgressLog((prev) => [...prev, `❌ Error: ${err}`]);
        },
      });
    } catch (e: any) {
      setIsLoading(false);
      setCurrentAgent(null);
      setCurrentStep(0);
      setErrorMsg(e.message || String(e));
    }
  };

  const toggleUnit = (unitNum: number) => {
    setExpandedUnits((prev) => ({ ...prev, [unitNum]: !prev[unitNum] }));
  };

  const toggleDayComplete = (dayNum: number) => {
    setCompletedDays((prev) => ({ ...prev, [dayNum]: !prev[dayNum] }));
  };

  const handleMCQAnswer = (
    topicId: string,
    qIndex: number,
    option: "A" | "B" | "C" | "D",
    correct: "A" | "B" | "C" | "D"
  ) => {
    const key = `${topicId}_q${qIndex}`;
    if (selectedAnswers[key]) return; // Answer already selected

    setSelectedAnswers((prev) => ({ ...prev, [key]: option }));

    if (option === correct) {
      setQuizScore((prev) => ({
        correct: prev.correct + 1,
        total: prev.total + 1,
      }));
    } else {
      setQuizScore((prev) => ({ ...prev, total: prev.total + 1 }));
    }
  };

  return (
    <div className="flex-1 w-full max-w-5xl mx-auto px-6 py-8 md:px-8 font-body text-hd-fg">
      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <header className="mb-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b-[3px] border-dashed border-hd-border pb-6">
        <div className="flex items-center gap-4">
          <div
            className="bg-hd-white border-[3px] border-hd-border p-3 shadow-hard"
            style={wobbly(0)}
          >
            <BookOpen
              className="w-7 h-7 text-hd-fg"
              strokeWidth={2.5}
            />
          </div>
          <div>
            <h1 className="text-4xl md:text-5xl font-heading font-bold text-hd-fg tracking-tight">
              StudyBits AI
              <span
                className="inline-block text-hd-accent ml-1 animate-bounce-gentle"
                aria-hidden="true"
              >
                !
              </span>
            </h1>
            <p className="text-base md:text-lg text-hd-fg/60 font-body mt-0.5">
              4-Agent Syllabus → Exam-Prep Engine
            </p>
          </div>
        </div>

        <div
          className="flex items-center gap-2.5 bg-hd-white border-2 border-hd-border px-4 py-2 shadow-hard-sm"
          style={wobbly(3)}
        >
          <span
            className={`inline-block w-3 h-3 border-2 border-hd-border ${
              backendAlive ? "bg-green-500" : "bg-hd-accent"
            }`}
            style={{ borderRadius: "50% 40% 50% 40%" }}
          />
          <span className="text-sm font-body font-bold text-hd-fg/70 uppercase tracking-wider">
            Backend: {backendAlive ? "Connected" : "Disconnected"}
          </span>
        </div>
      </header>

      {/* ─── Alerts ─────────────────────────────────────────────────────── */}
      {errorMsg && (
        <div
          className="mb-6 p-4 bg-hd-white border-[3px] border-hd-accent shadow-hard flex gap-3 items-start relative"
          style={wobbly(1)}
        >
          <AlertTriangle
            className="w-5 h-5 shrink-0 text-hd-accent"
            strokeWidth={3}
          />
          <div className="text-sm font-body">
            <span className="font-heading font-bold text-hd-accent">
              Oops!{" "}
            </span>
            {errorMsg}
          </div>
        </div>
      )}

      {successMsg && (
        <div
          className="mb-6 p-4 bg-hd-yellow border-[3px] border-hd-border shadow-hard flex gap-3 items-start relative"
          style={wobbly(2)}
        >
          <CheckCircle
            className="w-5 h-5 shrink-0 text-green-600"
            strokeWidth={3}
          />
          <div className="text-sm font-body">
            <span className="font-heading font-bold text-hd-fg">
              Awesome!{" "}
            </span>
            {successMsg}
          </div>
        </div>
      )}

      {/* ─── Main Dashboard ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* ─── Left Column: Control Panel ────────────────────────────── */}
        <section className="lg:col-span-4 flex flex-col gap-6">
          <div
            className="bg-hd-white border-[3px] border-hd-border p-6 shadow-hard relative tape-decoration"
            style={wobbly(0)}
          >
            <h2 className="text-lg font-heading font-bold text-hd-fg mb-4 underline-sketch inline-block">
              Configure Settings
            </h2>

            <form onSubmit={handleGenerate} className="flex flex-col gap-5">
              {/* Syllabus input */}
              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-sm font-body font-bold text-hd-fg/80">
                    Syllabus Text
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setSyllabus(SAMPLE_SYLLABUS);
                      setPdfFile(null);
                    }}
                    className="text-xs font-body font-bold text-hd-blue hover:text-hd-accent transition-colors duration-100"
                  >
                    ✎ Insert Sample
                  </button>
                </div>
                <textarea
                  value={syllabus}
                  onChange={(e) => setSyllabus(e.target.value)}
                  placeholder="Paste exam syllabus here..."
                  disabled={isLoading || pdfFile !== null}
                  rows={8}
                  className="w-full text-sm font-body bg-hd-white border-2 border-hd-border px-3.5 py-2.5 focus:outline-none focus:border-hd-blue focus:ring-2 focus:ring-hd-blue/20 disabled:opacity-50 placeholder:text-hd-fg/30 notebook-lines"
                  style={wobbly(1)}
                />
              </div>

              {/* PDF upload */}
              <div>
                <label className="block text-sm font-body font-bold text-hd-fg/80 mb-1.5">
                  Or Upload Syllabus PDF
                </label>
                <div
                  className="relative group flex flex-col items-center justify-center border-[3px] border-dashed border-hd-muted hover:border-hd-blue p-5 transition-colors duration-100 bg-hd-bg"
                  style={wobbly(2)}
                >
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                    disabled={isLoading}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                  />
                  <CloudUpload
                    className="w-7 h-7 text-hd-fg/30 mb-2 group-hover:text-hd-blue transition-colors duration-100"
                    strokeWidth={2.5}
                  />
                  <p className="text-sm font-body font-bold text-hd-fg/50 group-hover:text-hd-blue transition-colors duration-100">
                    {pdfFile
                      ? pdfFile.name
                      : "Drag & drop PDF or click to browse"}
                  </p>
                  {pdfFile && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setPdfFile(null);
                      }}
                      className="text-xs font-bold text-hd-accent hover:underline mt-1 z-10 flex items-center gap-1"
                    >
                      <X className="w-3 h-3" strokeWidth={3} />
                      Clear PDF
                    </button>
                  )}
                </div>
              </div>

              {/* Days Slider */}
              <div>
                <div className="flex justify-between text-sm font-body font-bold text-hd-fg/80 mb-2">
                  <span>Days until Exam</span>
                  <span
                    className="bg-hd-yellow border-2 border-hd-border px-2 py-0.5 text-hd-fg font-heading"
                    style={wobbly(3)}
                  >
                    {days} Days
                  </span>
                </div>
                <input
                  type="range"
                  min={3}
                  max={30}
                  step={1}
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  disabled={isLoading}
                  className="w-full cursor-pointer disabled:opacity-50"
                />
              </div>

              {/* Daily Hours Slider */}
              <div>
                <div className="flex justify-between text-sm font-body font-bold text-hd-fg/80 mb-2">
                  <span>Daily Study Hours</span>
                  <span
                    className="bg-hd-yellow border-2 border-hd-border px-2 py-0.5 text-hd-fg font-heading"
                    style={wobbly(4)}
                  >
                    {hours}h / day
                  </span>
                </div>
                <input
                  type="range"
                  min={1.0}
                  max={10.0}
                  step={0.5}
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                  disabled={isLoading}
                  className="w-full cursor-pointer disabled:opacity-50"
                />
              </div>

              {/* Student ID */}
              <div>
                <label className="block text-sm font-body font-bold text-hd-fg/80 mb-1.5">
                  Student ID
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    disabled={isLoading}
                    className="flex-1 text-sm font-body bg-hd-white border-2 border-hd-border px-3.5 py-2.5 focus:outline-none focus:border-hd-blue focus:ring-2 focus:ring-hd-blue/20 disabled:opacity-50"
                    style={wobbly(0)}
                  />
                  <button
                    type="button"
                    onClick={handleLoadSaved}
                    disabled={isLoading || !userId.trim()}
                    className="text-sm font-body font-bold px-4 py-2.5 bg-hd-muted border-2 border-hd-border text-hd-fg shadow-hard-sm hover:bg-hd-blue hover:text-white active:shadow-hard-none active:translate-x-[3px] active:translate-y-[3px] transition-all duration-100 disabled:opacity-50"
                    style={wobbly(1)}
                  >
                    Load
                  </button>
                </div>
              </div>

              {/* Generate Button */}
              <button
                type="submit"
                disabled={isLoading || (!syllabus.trim() && !pdfFile)}
                className="w-full py-3.5 bg-hd-white border-[3px] border-hd-border text-hd-fg font-heading font-bold text-xl shadow-hard hover:bg-hd-accent hover:text-white hover:shadow-hard-hover hover:translate-x-[2px] hover:translate-y-[2px] active:shadow-hard-none active:translate-x-[4px] active:translate-y-[4px] transition-all duration-100 disabled:opacity-50 disabled:hover:bg-hd-white disabled:hover:text-hd-fg disabled:hover:shadow-hard disabled:hover:translate-x-0 disabled:hover:translate-y-0 mt-2 flex items-center justify-center gap-2"
                style={wobbly(0)}
              >
                {isLoading ? (
                  <>
                    <Loader2
                      className="w-5 h-5 animate-spin"
                      strokeWidth={3}
                    />
                    <span>Scribbling Plan...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" strokeWidth={3} />
                    <span>Generate Prep Plan</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* ─── Pipeline Progress Tracker ────────────────────────────── */}
          {(isLoading || progressLog.length > 0) && (
            <div
              className="bg-hd-white border-[3px] border-hd-border p-5 shadow-hard relative tack-decoration"
              style={wobbly(1)}
            >
              <h3 className="text-base font-heading font-bold text-hd-fg mb-4 flex justify-between items-center">
                <span className="underline-sketch">Agent Progress</span>
                {isLoading && (
                  <span className="text-xs font-body text-hd-accent animate-pulse font-bold">
                    ● Running
                  </span>
                )}
              </h3>

              {/* Agent Flow Timeline */}
              <div className="flex flex-col gap-4 mb-5">
                {AGENT_STEPS.map((s, i) => {
                  const isActive = currentAgent === s.id;
                  const isCompleted =
                    currentStep > s.step ||
                    (!isLoading && progressLog.length > 1 && currentStep === 0);

                  let dotClass =
                    "bg-hd-muted border-hd-fg/30 text-hd-fg/40";
                  let labelClass = "text-hd-fg/40";

                  if (isActive) {
                    dotClass =
                      "bg-hd-accent border-hd-border text-white";
                    labelClass = "text-hd-fg font-bold";
                  } else if (isCompleted) {
                    dotClass =
                      "bg-green-500 border-hd-border text-white";
                    labelClass = "text-hd-fg/70";
                  }

                  return (
                    <div key={s.id} className="flex gap-3 items-start">
                      <div
                        className={`w-8 h-8 border-[3px] flex items-center justify-center text-xs font-heading font-bold shrink-0 transition-all duration-100 ${dotClass}`}
                        style={{
                          borderRadius: "50% 45% 55% 40% / 40% 55% 45% 50%",
                        }}
                      >
                        {isCompleted ? "✓" : s.step}
                      </div>
                      <div>
                        <div
                          className={`text-sm font-body ${labelClass} transition-all duration-100`}
                        >
                          {s.label}
                        </div>
                        {isActive && (
                          <div className="text-xs text-hd-fg/50 mt-0.5 font-body leading-relaxed">
                            {s.desc}
                          </div>
                        )}
                      </div>
                      {/* Dashed connector line (except last) */}
                      {i < AGENT_STEPS.length - 1 && (
                        <div className="hidden" />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Logs output */}
              <div className="border-t-2 border-dashed border-hd-muted pt-3">
                <div className="text-xs font-heading font-bold text-hd-fg/50 mb-1.5">
                  Pipeline Stream
                </div>
                <div
                  ref={logContainerRef}
                  className="bg-hd-bg border-2 border-hd-border p-3 h-32 overflow-y-auto font-body text-xs leading-relaxed text-hd-fg/70 flex flex-col gap-1 scrollbar-sketch notebook-lines"
                  style={wobbly(3)}
                >
                  {progressLog.map((log, index) => (
                    <div key={index} className="whitespace-pre-wrap">
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ─── Right Column: Content Tabs ─────────────────────────────── */}
        <section className="lg:col-span-8 flex flex-col gap-5 min-h-[500px]">
          {/* Tab Navigation */}
          <div className="flex flex-wrap gap-2">
            {(
              [
                { key: "topics", icon: FileText, label: "Syllabus Topics" },
                { key: "priority", icon: Target, label: "Priority Plan" },
                { key: "schedule", icon: Calendar, label: "Study Calendar" },
                { key: "content", icon: Brain, label: "Study Pack" },
              ] as const
            ).map((tab) => {
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-body font-bold border-[3px] transition-all duration-100 ${
                    isActive
                      ? "bg-hd-yellow border-hd-border shadow-hard-sm text-hd-fg -rotate-1"
                      : "bg-hd-white border-hd-border/30 text-hd-fg/50 hover:border-hd-border hover:text-hd-fg hover:rotate-1"
                  }`}
                  style={wobbly(
                    ["topics", "priority", "schedule", "content"].indexOf(
                      tab.key
                    )
                  )}
                >
                  <tab.icon className="w-4 h-4" strokeWidth={2.5} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Tab Content Area */}
          <div
            className="bg-hd-white border-[3px] border-hd-border p-6 shadow-hard flex-1"
            style={wobbly(2)}
          >
            {/* ─── 1. Topics Tab ───────────────────────────────────── */}
            {activeTab === "topics" && (
              <div className="flex flex-col gap-4">
                {!parsedTopics || !Array.isArray(parsedTopics.units) ? (
                  <EmptyState
                    icon="📋"
                    title="Topics hierarchy is empty"
                    desc="Run the pipeline. SyllabusParserAgent will extract units, estimated study hours, and topics automatically."
                  />
                ) : (
                  <div>
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-baseline mb-6 border-b-2 border-dashed border-hd-muted pb-4 gap-2">
                      <div>
                        <h3 className="text-2xl font-heading font-bold text-hd-fg">
                          {parsedTopics.course_name || "Parsed Syllabus"}
                        </h3>
                        <p className="text-sm text-hd-fg/50 mt-1 leading-relaxed font-body">
                          {parsedTopics.exam_pattern_notes}
                        </p>
                      </div>
                      <span
                        className="text-xs font-heading font-bold uppercase bg-hd-yellow border-2 border-hd-border px-3 py-1 shrink-0 shadow-hard-sm"
                        style={wobbly(3)}
                      >
                        {parsedTopics.total_units} Units
                      </span>
                    </div>

                    <div className="flex flex-col gap-4">
                      {parsedTopics.units.map((unit, unitIdx) => {
                        const isExpanded =
                          expandedUnits[unit.unit_number] !== false;
                        return (
                          <div
                            key={unit.unit_number}
                            className="border-[3px] border-hd-border overflow-hidden shadow-hard-sm"
                            style={wobbly(unitIdx % 3)}
                          >
                            <button
                              onClick={() => toggleUnit(unit.unit_number)}
                              className="w-full flex items-center justify-between px-5 py-4 bg-hd-bg text-left font-heading font-bold text-base text-hd-fg hover:bg-hd-yellow/50 transition-colors duration-100"
                            >
                              <span>
                                Unit {unit.unit_number} — {unit.unit_title}
                              </span>
                              <ChevronDown
                                className={`w-5 h-5 text-hd-fg/50 transition-transform duration-100 ${
                                  isExpanded ? "rotate-180" : ""
                                }`}
                                strokeWidth={3}
                              />
                            </button>

                            {isExpanded && (
                              <div className="divide-y-2 divide-dashed divide-hd-muted bg-hd-white">
                                {Array.isArray(unit.topics) &&
                                  unit.topics.map((t, tIdx) => (
                                    <div
                                      key={t.topic_id}
                                      className="p-5 flex flex-col gap-2"
                                    >
                                      <div className="flex flex-col sm:flex-row justify-between items-start gap-3">
                                        <div className="flex items-start gap-2">
                                          <span
                                            className="text-xs font-heading font-bold bg-hd-muted border-2 border-hd-border px-2 py-0.5 shrink-0"
                                            style={{
                                              borderRadius:
                                                "50% 40% 55% 45% / 45% 55% 40% 50%",
                                            }}
                                          >
                                            {t.topic_id}
                                          </span>
                                          <span className="font-body font-bold text-sm text-hd-fg">
                                            {t.title}
                                          </span>
                                        </div>

                                        <div className="flex gap-2 items-center">
                                          {t.marks_hint &&
                                            t.marks_hint !== "unknown" && (
                                              <span
                                                className="text-xs font-heading font-bold bg-hd-yellow border-2 border-hd-border px-2 py-0.5 shrink-0"
                                                style={wobbly(3)}
                                              >
                                                {t.marks_hint}
                                              </span>
                                            )}
                                          <span className="text-xs text-hd-fg/40 shrink-0 font-body font-bold flex items-center gap-1">
                                            <Clock
                                              className="w-3 h-3"
                                              strokeWidth={3}
                                            />
                                            {t.estimated_hours}h
                                          </span>
                                        </div>
                                      </div>

                                      {Array.isArray(t.subtopics) &&
                                        t.subtopics.length > 0 && (
                                          <div className="flex flex-wrap gap-1.5 mt-1">
                                            {t.subtopics.map((s, idx) => (
                                              <span
                                                key={idx}
                                                className="text-xs font-body bg-hd-bg border border-dashed border-hd-fg/30 text-hd-fg/60 px-2 py-0.5"
                                                style={wobbly(idx % 5)}
                                              >
                                                {s}
                                              </span>
                                            ))}
                                          </div>
                                        )}
                                    </div>
                                  ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ─── 2. Priority Tab ─────────────────────────────────── */}
            {activeTab === "priority" && (
              <div className="flex flex-col gap-4">
                {!priorityPlan ||
                !Array.isArray(priorityPlan.priority_ranked_topics) ? (
                  <EmptyState
                    icon="🎯"
                    title="Priority ranking is empty"
                    desc="Run the pipeline. TopicPrioritizerAgent will rank syllabus topics by weight, dependencies, and difficulty."
                  />
                ) : (
                  <div>
                    {/* Header stats */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                      {[
                        {
                          label: "Total Hours",
                          value: `${priorityPlan.total_study_hours_estimate}h`,
                          icon: Clock,
                          bg: "bg-hd-white",
                        },
                        {
                          label: "Quick Wins",
                          value: Array.isArray(priorityPlan.quick_wins)
                            ? priorityPlan.quick_wins.length
                            : 0,
                          icon: Star,
                          bg: "bg-hd-yellow",
                        },
                        {
                          label: "High Risk",
                          value: Array.isArray(priorityPlan.high_risk_topics)
                            ? priorityPlan.high_risk_topics.length
                            : 0,
                          icon: AlertTriangle,
                          bg: "bg-hd-white",
                        },
                      ].map((stat, idx) => (
                        <div
                          key={stat.label}
                          className={`${stat.bg} border-[3px] border-hd-border p-4 text-center shadow-hard-sm`}
                          style={{
                            borderRadius: [
                              "50% 45% 55% 40% / 40% 55% 45% 50%",
                              "45% 55% 40% 50% / 50% 40% 55% 45%",
                              "55% 40% 50% 45% / 45% 50% 40% 55%",
                            ][idx],
                          }}
                        >
                          <stat.icon
                            className="w-5 h-5 mx-auto mb-1 text-hd-fg/50"
                            strokeWidth={2.5}
                          />
                          <span className="block text-xs font-body font-bold uppercase text-hd-fg/50 mb-1">
                            {stat.label}
                          </span>
                          <span className="text-2xl md:text-3xl font-heading font-bold text-hd-fg">
                            {stat.value}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Rankings list */}
                    <div className="flex flex-col gap-4">
                      <h4 className="text-base font-heading font-bold text-hd-fg/60 underline-sketch inline-block">
                        Ranked Priority Road Map
                      </h4>

                      {priorityPlan.priority_ranked_topics.map((t) => {
                        const isQuickWin =
                          Array.isArray(priorityPlan.quick_wins) &&
                          priorityPlan.quick_wins.includes(t.topic_id);
                        const isHighRisk =
                          Array.isArray(priorityPlan.high_risk_topics) &&
                          priorityPlan.high_risk_topics.includes(t.topic_id);

                        let difficultyStyle = {
                          bg: "bg-hd-muted",
                          text: "text-hd-fg",
                          border: "border-hd-border/50",
                        };
                        if (t.difficulty === "Easy")
                          difficultyStyle = {
                            bg: "bg-green-100",
                            text: "text-green-800",
                            border: "border-green-600",
                          };
                        if (t.difficulty === "Medium")
                          difficultyStyle = {
                            bg: "bg-hd-yellow",
                            text: "text-amber-800",
                            border: "border-amber-600",
                          };
                        if (t.difficulty === "Hard")
                          difficultyStyle = {
                            bg: "bg-red-100",
                            text: "text-red-800",
                            border: "border-hd-accent",
                          };

                        return (
                          <div
                            key={t.topic_id}
                            className="border-[3px] border-hd-border p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-hard-sm hover:rotate-[0.3deg] hover:shadow-hard transition-all duration-100"
                            style={wobbly(t.rank % 5)}
                          >
                            <div className="flex items-start gap-4">
                              <div
                                className="w-10 h-10 bg-hd-yellow border-[3px] border-hd-border font-heading font-bold flex items-center justify-center shrink-0 shadow-hard-sm text-base"
                                style={{
                                  borderRadius:
                                    "50% 45% 55% 40% / 40% 55% 45% 50%",
                                }}
                              >
                                #{t.rank}
                              </div>

                              <div>
                                <div className="flex flex-wrap items-center gap-2 mb-1">
                                  <h5 className="font-heading font-bold text-base text-hd-fg">
                                    {t.title}
                                  </h5>
                                  <span
                                    className="text-xs font-body bg-hd-muted border border-dashed border-hd-fg/30 px-2 py-0.5 text-hd-fg/50 font-bold uppercase"
                                    style={wobbly(3)}
                                  >
                                    {t.topic_id}
                                  </span>
                                  {isQuickWin && (
                                    <span
                                      className="text-xs font-body font-bold bg-green-100 border-2 border-green-600 text-green-800 px-2 py-0.5"
                                      style={wobbly(2)}
                                    >
                                      ★ Quick Win
                                    </span>
                                  )}
                                  {isHighRisk && (
                                    <span
                                      className="text-xs font-body font-bold bg-red-100 border-2 border-hd-accent text-red-800 px-2 py-0.5"
                                      style={wobbly(4)}
                                    >
                                      ⚠ High Risk
                                    </span>
                                  )}
                                </div>
                                <span className="block text-xs text-hd-fg/40 font-body font-bold mb-1.5">
                                  {t.unit}
                                </span>
                                <p className="text-sm text-hd-fg/60 leading-relaxed font-body">
                                  {t.priority_reason}
                                </p>

                                {Array.isArray(t.must_study_before) &&
                                  t.must_study_before.length > 0 && (
                                    <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                                      <span className="text-xs font-body font-bold text-hd-fg/40 flex items-center gap-1">
                                        <ArrowRight
                                          className="w-3 h-3"
                                          strokeWidth={3}
                                        />
                                        Prereq for:
                                      </span>
                                      {t.must_study_before.map((dep, idx) => (
                                        <span
                                          key={idx}
                                          className="text-xs font-body font-bold bg-hd-bg border-2 border-hd-blue/50 text-hd-blue px-1.5 py-0.5"
                                          style={wobbly(idx % 5)}
                                        >
                                          {dep}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                              </div>
                            </div>

                            {/* Score & Diff Indicators */}
                            <div className="flex flex-row md:flex-col items-center md:items-end justify-between shrink-0 border-t-2 border-dashed border-hd-muted md:border-none pt-3 md:pt-0 gap-3 min-w-[120px]">
                              <span
                                className={`text-xs font-heading font-bold px-3 py-1 border-2 ${difficultyStyle.bg} ${difficultyStyle.text} ${difficultyStyle.border}`}
                                style={wobbly(2)}
                              >
                                {t.difficulty}
                              </span>

                              <div className="text-right">
                                <div className="text-xs font-body font-bold text-hd-fg/40 mb-1">
                                  Priority Weight
                                </div>
                                <div className="flex gap-1 justify-end">
                                  {Array.from({ length: 10 }).map((_, idx) => (
                                    <span
                                      key={idx}
                                      className={`inline-block w-2.5 h-2.5 border border-hd-border ${
                                        idx < t.priority_score
                                          ? "bg-hd-fg"
                                          : "bg-hd-muted"
                                      }`}
                                      style={{
                                        borderRadius:
                                          "50% 40% 55% 45% / 45% 55% 40% 50%",
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <span className="text-sm font-heading font-bold text-hd-fg/60 shrink-0 flex items-center gap-1">
                                <Clock
                                  className="w-3.5 h-3.5"
                                  strokeWidth={3}
                                />
                                {t.estimated_hours}h
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ─── 3. Schedule Tab ─────────────────────────────────── */}
            {activeTab === "schedule" && (
              <div className="flex flex-col gap-4">
                {!studySchedule ||
                !Array.isArray(studySchedule.schedule) ? (
                  <EmptyState
                    icon="📅"
                    title="Study Schedule is empty"
                    desc="Run the pipeline. ScheduleBuilderAgent will allocate topics to daily slots based on priority, hours, and days."
                  />
                ) : (
                  <div>
                    {/* Warnings Banner */}
                    {studySchedule.warnings &&
                      studySchedule.warnings.length > 0 && (
                        <div
                          className="mb-5 p-4 bg-hd-yellow border-[3px] border-hd-border shadow-hard-sm text-sm flex flex-col gap-1.5"
                          style={wobbly(1)}
                        >
                          <div className="font-heading font-bold flex items-center gap-2 text-hd-fg">
                            <AlertTriangle
                              className="w-5 h-5 text-hd-accent"
                              strokeWidth={3}
                            />
                            Schedule Warnings & Constraints:
                          </div>
                          <ul className="list-none pl-1 flex flex-col gap-0.5 font-body text-hd-fg/70">
                            {studySchedule.warnings.map((w, idx) => (
                              <li key={idx} className="flex items-start gap-2">
                                <span className="text-hd-accent shrink-0">
                                  ✗
                                </span>
                                {w}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                    {/* Timeline */}
                    <div className="flex flex-col gap-5">
                      {studySchedule.schedule.map((day, dayIdx) => {
                        const isRevision =
                          day.is_revision_day ||
                          studySchedule.revision_days?.includes(day.day);
                        const isCompleted = completedDays[day.day] === true;

                        let cardBg = "bg-hd-white";
                        let borderColor = "border-hd-border";
                        if (isRevision) {
                          cardBg = "bg-hd-yellow/40";
                          borderColor = "border-hd-blue";
                        }
                        if (isCompleted) {
                          cardBg = "bg-green-50";
                          borderColor = "border-green-600";
                        }

                        return (
                          <div
                            key={day.day}
                            className={`${cardBg} border-[3px] ${borderColor} p-5 md:p-6 shadow-hard-sm flex flex-col md:flex-row md:items-start justify-between gap-5 relative hover:rotate-[0.2deg] transition-transform duration-100`}
                            style={wobbly(dayIdx % 5)}
                          >
                            {/* Day ID & Checkbox */}
                            <div className="flex items-center md:items-start gap-4 shrink-0">
                              <button
                                onClick={() => toggleDayComplete(day.day)}
                                className={`w-7 h-7 border-[3px] flex items-center justify-center transition-all duration-100 shrink-0 ${
                                  isCompleted
                                    ? "bg-green-500 border-hd-border text-white"
                                    : "border-hd-border/50 hover:border-hd-border bg-hd-white"
                                }`}
                                style={{
                                  borderRadius:
                                    "50% 45% 55% 40% / 40% 55% 45% 50%",
                                }}
                              >
                                {isCompleted && (
                                  <span className="text-sm font-bold">✓</span>
                                )}
                              </button>

                              <div>
                                <span
                                  className={`inline-block text-sm font-heading font-bold px-3 py-1 mb-1 text-center shrink-0 border-2 border-hd-border ${
                                    isRevision
                                      ? "bg-hd-blue text-white shadow-hard-sm"
                                      : "bg-hd-muted text-hd-fg"
                                  }`}
                                  style={wobbly(3)}
                                >
                                  {day.label}
                                </span>
                                <span className="block text-xs text-hd-fg/40 font-body font-bold mt-1 flex items-center gap-1">
                                  <Clock
                                    className="w-3 h-3"
                                    strokeWidth={3}
                                  />
                                  {day.total_hours} Hours
                                </span>
                              </div>
                            </div>

                            {/* Daily Contents */}
                            <div className="flex-1">
                              <h4
                                className={`font-heading font-bold text-base mb-2.5 transition-all duration-100 ${
                                  isCompleted
                                    ? "line-through text-hd-fg/30"
                                    : "text-hd-fg"
                                }`}
                              >
                                {day.daily_goal}
                              </h4>

                              {isRevision ? (
                                <div
                                  className="text-sm text-hd-blue font-body font-bold flex items-center gap-2 bg-hd-blue/10 px-4 py-3 border-2 border-dashed border-hd-blue/50"
                                  style={wobbly(0)}
                                >
                                  <BookMarked
                                    className="w-5 h-5 shrink-0"
                                    strokeWidth={2.5}
                                  />
                                  Comprehensive Revision Day — study all
                                  completed topics and practice flashcards.
                                </div>
                              ) : (
                                <div className="flex flex-col gap-3">
                                  {Array.isArray(day.topics) &&
                                    day.topics.map((t) => (
                                      <div
                                        key={t.topic_id}
                                        className="bg-hd-bg border-2 border-hd-border/40 p-4"
                                        style={wobbly(1)}
                                      >
                                        <div className="flex justify-between items-baseline gap-4 mb-1">
                                          <div className="flex items-center gap-2">
                                            <span
                                              className="text-xs font-heading font-bold bg-hd-muted border-2 border-hd-border/40 px-2 py-0.5"
                                              style={{
                                                borderRadius:
                                                  "50% 40% 55% 45% / 45% 55% 40% 50%",
                                              }}
                                            >
                                              {t.topic_id}
                                            </span>
                                            <span className="font-body font-bold text-sm text-hd-fg/80">
                                              {t.title}
                                            </span>
                                          </div>
                                          <span className="text-xs text-hd-fg/40 font-heading font-bold shrink-0">
                                            {t.hours}h
                                          </span>
                                        </div>

                                        {t.study_tip && (
                                          <div
                                            className="text-xs text-hd-blue flex items-start gap-2 mt-2.5 font-body leading-relaxed bg-hd-white p-3 border-2 border-dashed border-hd-blue/30 relative"
                                            style={wobbly(2)}
                                          >
                                            <Lightbulb
                                              className="w-4 h-4 shrink-0 text-hd-blue"
                                              strokeWidth={2.5}
                                            />
                                            <span>{t.study_tip}</span>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ─── 4. Content Pack Tab ─────────────────────────────── */}
            {activeTab === "content" && (
              <div className="flex flex-col gap-4">
                {!contentPack || !Array.isArray(contentPack.topics) ? (
                  <EmptyState
                    icon="🧠"
                    title="Study pack is empty"
                    desc="Run the pipeline. ContentGeneratorAgent will build summaries, bullet notes, key terms, and multiple-choice questions for every topic."
                  />
                ) : (
                  <div>
                    {/* Quiz Score Header */}
                    <div
                      className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center bg-hd-white border-[3px] border-hd-border p-5 shadow-hard-sm gap-4"
                      style={wobbly(0)}
                    >
                      <div>
                        <h4 className="font-heading font-bold text-lg text-hd-fg">
                          Practice Quiz Tracker
                        </h4>
                        <p className="text-xs text-hd-fg/40 mt-0.5 font-body">
                          Score is updated instantly as you answer questions
                          below
                        </p>
                      </div>

                      <div
                        className="flex items-baseline gap-2 bg-hd-yellow border-[3px] border-hd-border px-5 py-2.5 font-heading font-bold text-lg shadow-hard-sm"
                        style={wobbly(3)}
                      >
                        <span className="text-hd-fg/60">Score:</span>
                        <span className="text-3xl text-hd-fg">
                          {quizScore.correct}
                        </span>
                        <span className="text-hd-fg/30">/</span>
                        <span className="text-xl text-hd-fg/50">
                          {quizScore.total}
                        </span>
                      </div>
                    </div>

                    {/* Content Pack items */}
                    <div className="flex flex-col gap-8">
                      {contentPack.topics.map((t, tIdx) => (
                        <div
                          key={t.topic_id}
                          className="border-[3px] border-hd-border overflow-hidden shadow-hard-sm"
                          style={wobbly(tIdx % 5)}
                        >
                          {/* Heading */}
                          <div className="bg-hd-bg border-b-[3px] border-dashed border-hd-border px-5 py-4">
                            <span className="text-xs font-heading font-bold uppercase tracking-widest text-hd-blue block mb-1">
                              {t.topic_id} · {t.unit}
                            </span>
                            <h4 className="font-heading font-bold text-xl text-hd-fg">
                              {t.title}
                            </h4>
                          </div>

                          <div className="p-5 md:p-6 flex flex-col gap-5">
                            {/* Summary */}
                            {t.summary && (
                              <div>
                                <h5 className="text-sm font-heading font-bold text-hd-fg/50 mb-2 underline-sketch inline-block">
                                  Study Notes Summary
                                </h5>
                                <div
                                  className="flex flex-col gap-2 bg-hd-bg p-4 border-2 border-hd-border/30 notebook-lines"
                                  style={wobbly(1)}
                                >
                                  {t.summary.split("\n").map((line, idx) => {
                                    const cleanLine = line
                                      .replace(/^\s*[•\-*]\s*/, "")
                                      .trim();
                                    if (!cleanLine) return null;
                                    return (
                                      <div
                                        key={idx}
                                        className="flex gap-2.5 items-start text-sm text-hd-fg/80 leading-relaxed font-body"
                                      >
                                        <span className="text-hd-accent shrink-0 font-bold">
                                          →
                                        </span>
                                        <span>{cleanLine}</span>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Key concepts */}
                            {t.key_concepts &&
                              t.key_concepts.length > 0 && (
                                <div>
                                  <h5 className="text-sm font-heading font-bold text-hd-fg/50 mb-2 underline-sketch inline-block">
                                    Key Concepts
                                  </h5>
                                  <div className="flex flex-wrap gap-2">
                                    {t.key_concepts.map((concept, idx) => (
                                      <span
                                        key={idx}
                                        className="text-sm font-body font-bold bg-hd-yellow border-2 border-hd-border px-3 py-1 shadow-hard-sm hover:rotate-1 transition-transform duration-100"
                                        style={wobbly(idx % 5)}
                                      >
                                        {concept}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}

                            {/* MCQs */}
                            {t.mcqs && t.mcqs.length > 0 && (
                              <div className="border-t-[3px] border-dashed border-hd-muted pt-5">
                                <h5 className="text-sm font-heading font-bold text-hd-fg/50 mb-4 underline-sketch inline-block">
                                  Practice Questions
                                </h5>

                                <div className="flex flex-col gap-6">
                                  {t.mcqs.map((q, qIdx) => {
                                    const qKey = `${t.topic_id}_q${qIdx}`;
                                    const selectedOpt = selectedAnswers[qKey];
                                    const isCorrect =
                                      selectedOpt === q.correct_answer;

                                    return (
                                      <div
                                        key={qIdx}
                                        className="bg-hd-bg border-[3px] border-hd-border/50 p-5 flex flex-col gap-3"
                                        style={wobbly(qIdx % 5)}
                                      >
                                        <div className="font-body font-bold text-sm leading-relaxed text-hd-fg flex items-start gap-2">
                                          <span
                                            className="bg-hd-accent text-white font-heading w-7 h-7 flex items-center justify-center shrink-0 text-xs border-2 border-hd-border"
                                            style={{
                                              borderRadius:
                                                "50% 45% 55% 40% / 40% 55% 45% 50%",
                                            }}
                                          >
                                            Q{qIdx + 1}
                                          </span>
                                          <span>{q.question}</span>
                                        </div>

                                        {/* Options */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-1">
                                          {(
                                            ["A", "B", "C", "D"] as const
                                          ).map((letter) => {
                                            const optionText =
                                              q.options[letter];
                                            if (!optionText) return null;

                                            const isSelected =
                                              selectedOpt === letter;
                                            const isCorrectLetter =
                                              letter === q.correct_answer;

                                            let optionBg = "bg-hd-white";
                                            let optionBorder =
                                              "border-hd-border/40 hover:border-hd-border";
                                            let optionText2 = "text-hd-fg/80";
                                            let prefixStyle = "text-hd-fg/40";

                                            if (selectedOpt) {
                                              if (isCorrectLetter) {
                                                optionBg = "bg-green-100";
                                                optionBorder =
                                                  "border-green-600";
                                                optionText2 =
                                                  "text-green-900 font-bold";
                                                prefixStyle =
                                                  "text-green-700 bg-green-200";
                                              } else if (isSelected) {
                                                optionBg = "bg-red-50";
                                                optionBorder =
                                                  "border-hd-accent";
                                                optionText2 =
                                                  "text-red-900 font-bold";
                                                prefixStyle =
                                                  "text-red-700 bg-red-200";
                                              } else {
                                                optionBg = "bg-hd-muted/30";
                                                optionBorder =
                                                  "border-hd-border/10";
                                                optionText2 =
                                                  "text-hd-fg/30";
                                                prefixStyle =
                                                  "text-hd-fg/20 bg-hd-muted/40";
                                              }
                                            }

                                            return (
                                              <button
                                                key={letter}
                                                type="button"
                                                onClick={() =>
                                                  handleMCQAnswer(
                                                    t.topic_id,
                                                    qIdx,
                                                    letter,
                                                    q.correct_answer
                                                  )
                                                }
                                                disabled={
                                                  selectedOpt !== undefined
                                                }
                                                className={`w-full flex items-start text-left border-2 px-4 py-3 transition-all duration-100 text-sm leading-relaxed font-body ${optionBg} ${optionBorder} ${optionText2} ${
                                                  !selectedOpt
                                                    ? "hover:shadow-hard-sm active:translate-x-[2px] active:translate-y-[2px]"
                                                    : ""
                                                }`}
                                                style={wobbly(
                                                  (qIdx + ["A", "B", "C", "D"].indexOf(letter)) % 5
                                                )}
                                              >
                                                <span
                                                  className={`font-heading font-bold mr-2 shrink-0 w-6 h-6 flex items-center justify-center border border-current text-xs ${prefixStyle}`}
                                                  style={{
                                                    borderRadius:
                                                      "50% 45% 55% 40% / 40% 55% 45% 50%",
                                                  }}
                                                >
                                                  {letter}
                                                </span>
                                                <span>{optionText}</span>
                                              </button>
                                            );
                                          })}
                                        </div>

                                        {/* Explanation */}
                                        {selectedOpt && (
                                          <div
                                            className={`mt-2 p-4 border-[3px] text-sm leading-relaxed font-body ${
                                              isCorrect
                                                ? "bg-green-50 border-green-600 text-green-900"
                                                : "bg-red-50 border-hd-accent text-red-900"
                                            }`}
                                            style={wobbly(2)}
                                          >
                                            <div className="font-heading font-bold mb-1 text-sm">
                                              {isCorrect
                                                ? "✓ Correct!"
                                                : `✗ Incorrect (Answer: ${q.correct_answer})`}
                                            </div>
                                            <span className="text-hd-fg/70">
                                              {q.explanation}
                                            </span>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* ─── Footer ───────────────────────────────────────────────────── */}
      <footer className="mt-16 text-center border-t-[3px] border-dashed border-hd-muted pt-6 pb-12">
        <p className="text-sm font-body font-bold text-hd-fg/40 tracking-wider rotate-[-0.5deg]">
          Sketched with ♥ using Google ADK, FastAPI & Next.js
        </p>
      </footer>
    </div>
  );
}

/* ─── EmptyState Component ──────────────────────────────────────────────── */

interface EmptyStateProps {
  icon: string;
  title: string;
  desc: string;
}

function EmptyState({ icon, title, desc }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center py-20 px-6 max-w-sm mx-auto border-[3px] border-dashed border-hd-muted"
      style={{
        borderRadius: "255px 15px 225px 15px / 15px 225px 15px 255px",
      }}
    >
      <span className="text-5xl mb-4 opacity-50 select-none">{icon}</span>
      <h3 className="font-heading font-bold text-lg text-hd-fg/60 mb-1">
        {title}
      </h3>
      <p className="text-sm text-hd-fg/40 leading-relaxed font-body">{desc}</p>
    </div>
  );
}
