import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { format } from "date-fns";
import { RefreshCw, Upload, Search, XCircle } from "lucide-react";
import { useCalls } from "@/hooks/useCalls";
import { useAgents } from "@/hooks/useAgents";
import { StatusBadge } from "@/components/ui/badge";
import DispositionBadge from "@/components/calls/DispositionBadge";
import { cancelCall } from "@/api/calls";
import { useQueryClient } from "@tanstack/react-query";
import type { CallStatus } from "@/types";

const STAGE_PROGRESS: Record<string, { pct: number; label: string; color: string }> = {
  QUEUED:       { pct: 8,   label: "Queued — waiting to start",        color: "bg-gray-400" },
  TRANSCRIBING: { pct: 30,  label: "Transcribing audio…",              color: "bg-blue-500" },
  ANALYZING:    { pct: 60,  label: "Analyzing speech features…",       color: "bg-indigo-500" },
  SCORING:      { pct: 85,  label: "Scoring with AI…",                 color: "bg-violet-500" },
};

function ProcessingBar({ callId, status, onCancel }: { callId: string; status: string; onCancel: (id: string) => void }) {
  const stage = STAGE_PROGRESS[status];
  if (!stage) return null;
  return (
    <tr>
      <td colSpan={8} className="px-5 pb-2.5 pt-0">
        <div className="flex items-center gap-3">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${stage.color} ${status !== "QUEUED" ? "animate-pulse" : ""}`}
              style={{ width: `${stage.pct}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">{stage.pct}% · {stage.label}</span>
          <button
            onClick={(e) => { e.stopPropagation(); onCancel(callId); }}
            title="Cancel processing"
            className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 px-2 py-0.5 rounded transition-colors whitespace-nowrap"
          >
            <XCircle size={12} />
            Stop
          </button>
        </div>
      </td>
    </tr>
  );
}

const STATUS_OPTIONS: { label: string; value: string }[] = [
  { label: "All statuses", value: "" },
  { label: "Queued", value: "QUEUED" },
  { label: "Transcribing", value: "TRANSCRIBING" },
  { label: "Analyzing", value: "ANALYZING" },
  { label: "Scoring", value: "SCORING" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Failed", value: "FAILED" },
];

function formatDuration(seconds: number | null): string {
  if (!seconds) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return "—";
  return score.toFixed(0);
}

export default function CallsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [agentId, setAgentId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);

  const { data: agents = [] } = useAgents();
  const { data, isLoading, isFetching, refetch } = useCalls({
    page,
    limit: 20,
    agent_id: agentId || undefined,
    status: statusFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  const calls = data?.data ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 0;

  async function handleCancel(callId: string) {
    if (cancelling) return;
    setCancelling(callId);
    try {
      await cancelCall(callId);
      queryClient.invalidateQueries({ queryKey: ["calls"] });
    } finally {
      setCancelling(null);
    }
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Calls</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} total call{total !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            onClick={() => navigate("/upload")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium transition-colors"
          >
            <Upload size={14} />
            Upload call
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={agentId}
          onChange={(e) => { setAgentId(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All agents</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.full_name}</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="To date"
        />

        {(agentId || statusFilter || dateFrom || dateTo) && (
          <button
            onClick={() => { setAgentId(""); setStatusFilter(""); setDateFrom(""); setDateTo(""); setPage(1); }}
            className="px-3 py-2 rounded-lg text-sm text-red-600 hover:bg-red-50 border border-red-200 transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <RefreshCw size={20} className="animate-spin mr-2" /> Loading calls…
          </div>
        ) : calls.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <Search size={32} className="mb-3 opacity-40" />
            <p className="text-sm font-medium">No calls found</p>
            <p className="text-xs mt-1">Try adjusting your filters or upload a call</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">File</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Duration</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Disposition</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Speech</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Sales</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {calls.map((call) => (
                <>
                <tr
                  key={call.id}
                  onClick={() => navigate(`/calls/${call.id}`)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3.5 text-gray-700 whitespace-nowrap">
                    {format(new Date(call.call_date), "dd MMM yyyy")}
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap">
                    <Link
                      to={`/agents/${call.agent_id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-medium text-gray-900 hover:text-brand-600 transition-colors"
                    >
                      {call.agent_name}
                    </Link>
                  </td>
                  <td className="px-5 py-3.5 text-gray-500 max-w-[180px] truncate" title={call.original_filename}>
                    {call.original_filename}
                  </td>
                  <td className="px-5 py-3.5 text-gray-700 whitespace-nowrap">{formatDuration(call.duration_seconds)}</td>
                  <td className="px-5 py-3.5">
                    <StatusBadge status={call.status as CallStatus} />
                  </td>
                  <td className="px-5 py-3.5">
                    {call.disposition ? <DispositionBadge disposition={call.disposition} size="sm" /> : <span className="text-gray-400 text-xs">—</span>}
                  </td>
                  <td className="px-5 py-3.5 text-right font-medium">
                    {call.speech_score !== null ? (
                      <span className={
                        call.speech_score >= 80 ? "text-green-600" :
                        call.speech_score >= 60 ? "text-yellow-600" :
                        call.speech_score >= 40 ? "text-orange-600" : "text-red-600"
                      }>
                        {formatScore(call.speech_score)}
                      </span>
                    ) : <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-5 py-3.5 text-right font-medium">
                    {call.sales_score !== null ? (
                      <span className={
                        call.sales_score >= 80 ? "text-green-600" :
                        call.sales_score >= 60 ? "text-yellow-600" :
                        call.sales_score >= 40 ? "text-orange-600" : "text-red-600"
                      }>
                        {formatScore(call.sales_score)}
                      </span>
                    ) : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
                {STAGE_PROGRESS[call.status] && <ProcessingBar key={`bar-${call.id}`} callId={call.id} status={call.status} onCancel={handleCancel} />}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-600">
          <span>Page {page} of {pages}</span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
