import { useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, FileText, BarChart2, MessageSquare, Lightbulb } from "lucide-react";
import { format } from "date-fns";

import { fetchCall, fetchTranscript, fetchAudioUrl, fetchScores, fetchSummary, fetchCoaching } from "@/api/calls";
import { StatusBadge } from "@/components/ui/badge";
import AudioPlayer, { type AudioPlayerHandle } from "@/components/calls/AudioPlayer";
import TranscriptViewer from "@/components/calls/TranscriptViewer";
import SpeechScoreRadar from "@/components/calls/SpeechScoreRadar";
import SalesScoreRadar from "@/components/calls/SalesScoreRadar";
import SummaryCard from "@/components/calls/SummaryCard";
import DispositionBadge from "@/components/calls/DispositionBadge";
import CoachingTab from "@/components/calls/CoachingTab";
import type { CallStatus } from "@/types";
import { clsx } from "clsx";

type Tab = "transcript" | "scores" | "summary" | "coaching";

const TABS: { id: Tab; label: string; icon: typeof FileText }[] = [
  { id: "transcript", label: "Transcript", icon: FileText },
  { id: "scores", label: "Scores", icon: BarChart2 },
  { id: "summary", label: "Summary", icon: MessageSquare },
  { id: "coaching", label: "Coaching", icon: Lightbulb },
];

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<Tab>("transcript");
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const playerRef = useRef<AudioPlayerHandle>(null);

  const { data: call, isLoading: callLoading } = useQuery({
    queryKey: ["call", id],
    queryFn: () => fetchCall(id!),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data && !["COMPLETED", "FAILED"].includes(query.state.data.status) ? 10_000 : false,
  });

  const isCompleted = call?.status === "COMPLETED";

  const { data: transcript, isLoading: transcriptLoading } = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => fetchTranscript(id!),
    enabled: !!id && isCompleted,
    retry: false,
  });

  const { data: audioUrl } = useQuery({
    queryKey: ["audio-url", id],
    queryFn: () => fetchAudioUrl(id!),
    enabled: !!id && isCompleted,
    staleTime: 90 * 60 * 1000, // presigned URL valid for 2h, refetch before expiry
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
        <StatusBadge status={call.status as CallStatus} />
      </div>

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
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "transcript" && (
        <div className="space-y-4">
          {/* Audio player */}
          {isCompleted && audioUrl ? (
            <AudioPlayer
              ref={playerRef}
              audioUrl={audioUrl}
              onTimeUpdate={setCurrentTimeMs}
            />
          ) : (
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm text-gray-400 flex items-center gap-2">
              <Clock size={16} />
              Audio player available once processing completes.
            </div>
          )}

          {/* Transcript */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 h-[500px] flex flex-col">
            {transcriptLoading ? (
              <div className="flex items-center gap-2 text-sm text-gray-400 animate-pulse m-auto">
                <Clock size={16} /> Loading transcript…
              </div>
            ) : transcript ? (
              <TranscriptViewer
                segments={transcript.segments}
                currentTimeMs={currentTimeMs}
                onSeek={handleSeek}
              />
            ) : isCompleted ? (
              <div className="text-sm text-gray-400 m-auto">
                Transcript not available for this call.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400 m-auto">
                <Clock size={16} />
                Transcript will appear once the call finishes processing.
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
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Speech Quality</h3>
            {scores?.speech ? (
              <SpeechScoreRadar score={scores.speech} />
            ) : isCompleted ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Speech scores not yet available.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Scores will appear once processing completes.
              </div>
            )}
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Sales Quality</h3>
            {scores?.sales ? (
              <SalesScoreRadar score={scores.sales} />
            ) : isCompleted ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Sales scores not yet available.
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <BarChart2 size={16} /> Scores will appear once processing completes.
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
              <span className="text-sm">Summary not yet available for this call.</span>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-gray-400">
              <MessageSquare size={20} />
              <span className="text-sm">Summary will appear once the call finishes processing.</span>
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
