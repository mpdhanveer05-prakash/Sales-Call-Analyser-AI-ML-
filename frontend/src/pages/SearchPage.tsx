import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Search, Filter, Clock, AlertCircle } from "lucide-react";
import { format } from "date-fns";
import { searchCalls } from "@/api/search";
import { useAgents } from "@/hooks/useAgents";
import DispositionBadge from "@/components/calls/DispositionBadge";
import type { SearchResult } from "@/types";

const DISPOSITIONS = [
  "CONVERTED", "INTERESTED_FOLLOWUP", "INTERESTED_NO_NEXTSTEP",
  "OBJECTION_PRICE", "OBJECTION_TIMING", "OBJECTION_AUTHORITY",
  "OBJECTION_NEED", "OBJECTION_COMPETITOR", "NOT_INTERESTED",
  "CALLBACK_REQUESTED", "VOICEMAIL", "NO_ANSWER", "WRONG_NUMBER",
  "GATEKEEPER", "DNC", "PARTIAL_CALL", "LANGUAGE_BARRIER", "OTHER",
];

function scoreColor(v: number | null) {
  if (v === null) return "text-gray-400";
  if (v >= 80) return "text-emerald-600";
  if (v >= 60) return "text-yellow-600";
  if (v >= 40) return "text-orange-500";
  return "text-red-600";
}

function Highlight({ html }: { html: string }) {
  return (
    <span
      className="text-sm text-gray-700 leading-relaxed [&_mark]:bg-yellow-200 [&_mark]:rounded [&_mark]:px-0.5"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function ResultCard({ result, onClick }: { result: SearchResult; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl border border-gray-200 p-4 hover:border-blue-300 hover:shadow-sm cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <p className="font-semibold text-gray-900 text-sm">{result.agent_name ?? "Unknown Agent"}</p>
          <p className="text-xs text-gray-500">
            {result.call_date ? format(new Date(result.call_date), "dd MMM yyyy") : "—"}
            {result.duration_seconds && (
              <span> · {Math.floor(result.duration_seconds / 60)}m {result.duration_seconds % 60}s</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {result.disposition && <DispositionBadge disposition={result.disposition} size="sm" />}
          {result.speech_score !== null && (
            <span className={`text-xs font-bold ${scoreColor(result.speech_score)}`}>
              S:{result.speech_score?.toFixed(0)}
            </span>
          )}
          {result.sales_score !== null && (
            <span className={`text-xs font-bold ${scoreColor(result.sales_score)}`}>
              Q:{result.sales_score?.toFixed(0)}
            </span>
          )}
        </div>
      </div>

      {result.highlights.length > 0 && (
        <div className="space-y-1 mt-2 border-t border-gray-100 pt-2">
          {result.highlights.slice(0, 2).map((hl, i) => (
            <Highlight key={i} html={hl} />
          ))}
        </div>
      )}

      {result.matched_segment && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-blue-600">
          <Clock size={11} />
          Jump to {Math.floor(result.matched_segment.start_ms / 60000)}:
          {String(Math.floor((result.matched_segment.start_ms % 60000) / 1000)).padStart(2, "0")}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  const navigate = useNavigate();
  const { data: agents = [] } = useAgents();

  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState<"keyword" | "semantic">("keyword");
  const [agentId, setAgentId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [disposition, setDisposition] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const { mutate, data: results, isPending, error } = useMutation({
    mutationFn: () =>
      searchCalls({
        query,
        search_type: searchType,
        agent_id: agentId || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        disposition: disposition || undefined,
        limit: 20,
      }),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) mutate();
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Search Transcripts</h1>
      <p className="text-sm text-gray-500 mb-6">Search across all call transcripts for keywords, phrases, or topics.</p>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="space-y-3 mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search transcripts…"
              className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Type toggle */}
          <div className="flex rounded-lg border border-gray-300 overflow-hidden">
            {(["keyword", "semantic"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setSearchType(t)}
                className={`px-3 py-2 text-xs font-medium transition-colors ${
                  searchType === t
                    ? "bg-brand-600 text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowFilters((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition-colors ${
              showFilters ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300 text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Filter size={14} />
            Filters
          </button>

          <button
            type="submit"
            disabled={!query.trim() || isPending}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {isPending ? "Searching…" : "Search"}
          </button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap gap-3 p-4 bg-gray-50 rounded-xl border border-gray-200">
            <select
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All agents</option>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
            </select>

            <select
              value={disposition}
              onChange={(e) => setDisposition(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">All dispositions</option>
              {DISPOSITIONS.map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
            </select>

            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        )}
      </form>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4">
          <AlertCircle size={16} /> Search failed. Make sure OpenSearch is running.
        </div>
      )}

      {/* Results */}
      {results !== undefined && (
        <div>
          <p className="text-xs text-gray-500 mb-3">
            {results.length === 0 ? "No results found." : `${results.length} result${results.length !== 1 ? "s" : ""} found.`}
          </p>
          <div className="space-y-3">
            {results.map((r) => (
              <ResultCard
                key={r.call_id}
                result={r}
                onClick={() => navigate(`/calls/${r.call_id}`)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Empty state before first search */}
      {results === undefined && !isPending && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Search size={36} className="mb-3 opacity-30" />
          <p className="text-sm">Enter a keyword or phrase to search call transcripts.</p>
        </div>
      )}
    </div>
  );
}
