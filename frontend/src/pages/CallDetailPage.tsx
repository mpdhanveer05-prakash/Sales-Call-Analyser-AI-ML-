import { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, FileText, BarChart2, MessageSquare, Lightbulb, Trash2, Download, ChevronDown, Loader2 } from "lucide-react";
import { format } from "date-fns";

import { fetchCall, fetchTranscript, fetchAudioUrl, fetchScores, fetchSummary, fetchCoaching, deleteCall } from "@/api/calls";
import { StatusBadge } from "@/components/ui/badge";
import AudioPlayer, { type AudioPlayerHandle } from "@/components/calls/AudioPlayer";
import TranscriptViewer from "@/components/calls/TranscriptViewer";
import SpeechScoreRadar from "@/components/calls/SpeechScoreRadar";
import SalesScoreRadar from "@/components/calls/SalesScoreRadar";
import SummaryCard from "@/components/calls/SummaryCard";
import DispositionBadge from "@/components/calls/DispositionBadge";
import CoachingTab from "@/components/calls/CoachingTab";
import { toast } from "@/store/toastStore";
import type { CallStatus } from "@/types";
import { clsx } from "clsx";

type Tab = "transcript" | "scores" | "summary" | "coaching";

const TABS: { id: Tab; label: string; icon: typeof FileText }[] = [
  { id: "transcript", label: "Transcript", icon: FileText },
  { id: "scores", label: "Scores", icon: BarChart2 },
  { id: "summary", label: "Summary", icon: MessageSquare },
  { id: "coaching", label: "Coaching", icon: Lightbulb },
];

const PROCESSING_STATUSES = new Set(["QUEUED", "TRANSCRIBING", "ANALYZING", "SCORING"]);

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<Tab>("transcript");
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [exportOpen, setExportOpen] = useState(false);
  const playerRef = useRef<AudioPlayerHandle>(null);
  const prevStatusRef = useRef<string | undefined>(undefined);

  const { data: call, isLoading: callLoading } = useQuery({
    queryKey: ["call", id],
    queryFn: () => fetchCall(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s && PROCESSING_STATUSES.has(s) ? 5_000 : false;
    },
  });

  // Fire toasts on status transitions
  useEffect(() => {
    if (!call?.status) return;
    const prev = prevStatusRef.current;
    const curr = call.status;
    if (prev !== undefined && prev !== curr) {
      if (curr === "ANALYZING") {
        toast.success("Transcript is ready! Analyzing speech now…");
      } else if (curr === "SCORING") {
        toast.info("Speech analysis complete — scoring with AI…");
      } else if (curr === "COMPLETED") {
        toast.success("All scores are ready!");
      } else if (curr === "FAILED") {
        toast.error("Processing failed for this call.");
      } else if (curr === "CANCELLED") {
        toast.warning("Processing was cancelled.");
      }
    }
    prevStatusRef.current = curr;
  }, [call?.status]);

  const isCompleted = call?.status === "COMPLETED";
  // Transcript is available as soon as transcription finishes (status moves to ANALYZING or beyond)
  const transcriptAvailable = !!call && !["QUEUED", "TRANSCRIBING"].includes(call.status);

  const { data: transcript, isLoading: transcriptLoading } = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => fetchTranscript(id!),
    enabled: !!id && transcriptAvailable,
    retry: 2,
    retryDelay: 3000,
  });

  const { data: audioUrl } = useQuery({
    queryKey: ["audio-url", id],
    queryFn: () => fetchAudioUrl(id!),
    enabled: !!id && isCompleted,
    staleTime: 90 * 60 * 1000,
  });

  const { data: scores } = useQuery({
    queryKey: ["scores", id],
    queryFn: () => fetchScores(id!),
    enabled: !!id && isCompleted,
    retry: false,
  });

  const { data: summary } = useQuery({
    queryKey: ["summary", id],
    queryFn: () => fetchSummary(id!),
    enabled: !!id && isCompleted,
    retry: false,
  });

  const { data: coaching } = useQuery({
    queryKey: ["coaching", id],
    queryFn: () => fetchCoaching(id!),
    enabled: !!id && isCompleted,
    retry: false,
  });

  const handleSeek = (ms: number) => {
    playerRef.current?.seekTo(ms);
  };

  async function handleDelete() {
    if (!window.confirm("Delete this call? This cannot be undone.")) return;
    try {
      await deleteCall(id!);
      navigate("/calls");
    } catch {
      alert("Failed to delete call. Please try again.");
    }
  }

  function exportTranscript() {
    if (!transcript || !call) return;
    const lines = transcript.segments.map(
      (s) => `[${s.speaker}] ${Math.floor(s.start_ms / 1000)}s: ${s.text}`
    );
    const header = `Call: ${call.original_filename}\nAgent: ${call.agent_name}\nDate: ${format(new Date(call.call_date), "dd MMM yyyy")}\n\n`;
    const blob = new Blob([header + lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript_${id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    setExportOpen(false);
  }

  function exportScoresCSV() {
    if (!scores || !call) return;
    const rows: string[][] = [["Category", "Dimension", "Score"]];
    if (scores.speech) {
      const s = scores.speech;
      (
        [
          ["Speech", "Pronunciation", s.pronunciation],
          ["Speech", "Intonation", s.intonation],
          ["Speech", "Fluency", s.fluency],
          ["Speech", "Grammar", s.grammar],
          ["Speech", "Vocabulary", s.vocabulary],
          ["Speech", "Pace", s.pace],
          ["Speech", "Clarity", s.clarity],
          ["Speech", "Filler Score", s.filler_score],
          ["Speech", "Composite", s.composite],
        ] as [string, string, number][]
      ).forEach(([cat, dim, val]) => rows.push([cat, dim, Number(val).toFixed(1)]));
    }
    if (scores.sales) {
      const s = scores.sales;
      (
        [
          ["Sales", "Greeting", s.greeting],
          ["Sales", "Rapport", s.rapport],
          ["Sales", "Discovery", s.discovery],
          ["Sales", "Value Explanation", s.value_explanation],
          ["Sales", "Objection Handling", s.objection_handling],
          ["Sales", "Script Adherence", s.script_adherence],
          ["Sales", "Closing", s.closing],
          ["Sales", "Compliance", s.compliance],
          ["Sales", "Composite", s.composite],
        ] as [string, string, number][]
      ).forEach(([cat, dim, val]) => rows.push([cat, dim, Number(val).toFixed(1)]));
    }
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scores_${id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setExportOpen(false);
  }

  function printReport() {
    setExportOpen(false);
    setTimeout(() => window.print(), 100);
  }

  if (callLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Loading call…
      </div>
    );
  }

  if (!call) {
    return <div className="p-8 text-gray-500 text-sm">Call not found.</div>;
  }

  const durationLabel = call.duration_seconds
    ? `${Math.floor(call.duration_seconds / 60)}m ${call.duration_seconds % 60}s`
    : "—";

  const isProcessing = PROCESSING_STATUSES.has(call.status);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Back */}
      <button
        onClick={() => navigate("/calls")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5 transition-colors"
      >
        <ArrowLeft size={14} />
        Back to calls
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-900 truncate max-w-lg">{call.original_filename}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {call.agent_name} · {format(new Date(call.call_date), "dd MMM yyyy")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={call.status as CallStatus} />
          <div className="relative">
            <button
              onClick={() => setExportOpen((o) => !o)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Download size={13} />
              Export
              <ChevronDown size={12} className={exportOpen ? "rotate-180 transition-transform" : "transition-transform"} />
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1">
                <button
                  onClick={exportTranscript}
                  disabled={!transcript}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  Transcript (.txt)
                </button>
                <button
                  onClick={exportScoresCSV}
                  disabled={!scores?.speech && !scores?.sales}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:text-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  Scores (.csv)
                </button>
                <button
                  onClick={printReport}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Print report
                </button>
              </div>
            )}
          </div>
          <button
            onClick={handleDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            <Trash2 size={13} />
            Delete
          </button>
        </div>
      </div>

      {/* Processing banner */}
      {isProcessing && (
        <div className="flex items-center gap-2.5 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-xl mb-5 text-sm text-blue-700">
          <Loader2 size={14} className="animate-spin flex-shrink-0" />
          <span>
            {call.status === "QUEUED" && "Waiting in queue…"}
            {call.status === "TRANSCRIBING" && "Transcribing audio — transcript will appear automatically when ready."}
            {call.status === "ANALYZING" && "Transcript ready · Analyzing speech features…"}
            {call.status === "SCORING" && "Speech analysis done · Scoring with AI — almost there…"}
          </span>
        </div>
      )}

      {/* Metadata cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {[
          { label: "Speech Score", value: call.speech_score?.toFixed(0) ?? "—" },
          { label: "Sales Score", value: call.sales_score?.toFixed(0) ?? "—" },
          { label: "Duration", value: durationLabel },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
            <p className="text-lg font-bold text-gray-900">{value}</p>
          </div>
        ))}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Disposition</p>
          {call.disposition ? (
            <DispositionBadge disposition={call.disposition} />
          ) : (
            <p className="text-lg font-bold text-gray-900">—</p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-5">
        <nav className="flex gap-1">
          {TABS.map(({ id: tabId, label, icon: Icon }) => (
            <button
              key={tabId}
              onClick={() => setActiveTab(tabId)}
              className={clsx(
                "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
                activeTab === tabId
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              <Icon size={14} />
              {label}
              {/* Dot indicator when data is live but call not complete */}
              {tabId === "transcript" && transcript && !isCompleted && (
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "transcript" && (
        <div className="space-y-4">
          {/* Audio player — only once processing is fully done */}
          {isCompleted && audioUrl ? (
            <AudioPlayer
              ref={playerRef}
              audioUrl={audioUrl}
              onTimeUpdate={setCurrentTimeMs}
            />
          ) : isProcessing ? null : (
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-400 flex items-center gap-2">
              <Clock size={16} />
              Audio player available once processing completes.
            </div>
          )}

          {/* Scores-still-computing notice when transcript is available but scores aren't */}
          {transcript && !isCompleted && isProcessing && (
            <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
              <Loader2 size={13} className="animate-spin flex-shrink-0" />
              Scores and summary are still computing — transcript is available now.
            </div>
          )}

          {/* Transcript */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 h-[500px] flex flex-col">
            {transcriptLoading ? (
              <div className="flex items-center gap-2 text-sm text-gray-400 animate-pulse m-auto">
                <Loader2 size={16} className="animate-spin" /> Loading transcript…
              </div>
            ) : transcript ? (
              <TranscriptViewer
                segments={transcript.segments}
                currentTimeMs={currentTimeMs}
                onSeek={handleSeek}
              />
            ) : transcriptAvailable ? (
              <div className="text-sm text-gray-400 m-auto">
                Transcript not available for this call.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400 m-auto">
                <Loader2 size={16} className="animate-spin" />
                Transcript will appear automatically once transcription finishes.
              </div>
            )}
          </div>

          {/* Transcript stats */}
          {transcript && (
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Total Segments", value: transcript.segment_count },
                {
                  label: "Agent Turns",
                  value: transcript.segments.filter((s) => s.speaker === "AGENT").length,
                },
                {
                  label: "Customer Turns",
                  value: transcript.segments.filter((s) => s.speaker === "CUSTOMER").length,
                },
              ].map(({ label, value }) => (
                <div key={label} className="bg-white rounded-xl border border-gray-200 p-3 text-center">
                  <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
                  <p className="text-xl font-bold text-gray-900 mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "scores" && (
        <div className="space-y-4">
          {/* Computing indicator */}
          {isProcessing && (
            <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
              <Loader2 size={13} className="animate-spin flex-shrink-0" />
              {call.status === "ANALYZING"
                ? "Analyzing speech features — scores will appear when complete."
                : "Scoring with AI — this may take a few minutes."}
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Speech Quality</h3>
            {scores?.speech ? (
              <SpeechScoreRadar score={scores.speech} />
            ) : isCompleted ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Speech scores not available.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 size={16} className="animate-spin" /> Waiting for scores…
              </div>
            )}
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Sales Quality</h3>
            {scores?.sales ? (
              <SalesScoreRadar score={scores.sales} />
            ) : isCompleted ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Sales scores not available.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <Loader2 size={16} className="animate-spin" /> Waiting for scores…
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "summary" && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          {summary ? (
            <div className="space-y-4">
              {call.disposition && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Outcome</span>
                  <DispositionBadge disposition={call.disposition} />
                </div>
              )}
              <SummaryCard summary={summary} />
            </div>
          ) : isCompleted ? (
            <div className="flex items-center gap-3 text-gray-400">
              <MessageSquare size={20} />
              <span className="text-sm">Summary not available for this call.</span>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-blue-600">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm">Summary will be generated once all processing completes.</span>
            </div>
          )}
        </div>
      )}

      {activeTab === "coaching" && (
        <CoachingTab
          callId={id!}
          clips={coaching?.coaching_clips ?? []}
          objections={coaching?.objections ?? []}
          onSeek={handleSeek}
        />
      )}
    </div>
  );
}
