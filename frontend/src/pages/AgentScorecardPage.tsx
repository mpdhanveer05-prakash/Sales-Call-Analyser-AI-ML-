import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, TrendingUp, TrendingDown, Phone, User, Download, ChevronDown } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
} from "recharts";
import { fetchAgentScorecard } from "@/api/agents";
import { fetchCalls } from "@/api/calls";
import DispositionBadge from "@/components/calls/DispositionBadge";
import { format } from "date-fns";

const PERIOD_OPTIONS = [
  { label: "Last 7 days", value: 7 },
  { label: "Last 30 days", value: 30 },
  { label: "Last 90 days", value: 90 },
];

function scoreColor(v: number | null) {
  if (v === null) return "text-gray-400";
  if (v >= 80) return "text-emerald-600";
  if (v >= 60) return "text-yellow-600";
  if (v >= 40) return "text-orange-500";
  return "text-red-600";
}

function ScoreHero({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 text-center">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-4xl font-black ${scoreColor(value)}`}>
        {value !== null ? value.toFixed(0) : "—"}
      </p>
      <p className="text-xs text-gray-400 mt-0.5">out of 100</p>
    </div>
  );
}

function DimLabel({ dim }: { dim: string }) {
  const [prefix, name] = dim.includes(":") ? dim.split(":") : ["", dim];
  return (
    <span className="text-xs">
      <span className="text-gray-400 mr-1">{prefix}</span>
      <span className="font-medium text-gray-700 capitalize">{name.replace(/_/g, " ")}</span>
    </span>
  );
}

export default function AgentScorecardPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [period, setPeriod] = useState(30);
  const [exportOpen, setExportOpen] = useState(false);

  const { data: scorecard, isLoading, isError } = useQuery({
    queryKey: ["scorecard", id, period],
    queryFn: () => fetchAgentScorecard(id!, period),
    enabled: !!id,
    retry: false,
  });

  const { data: recentCalls } = useQuery({
    queryKey: ["calls", { agent_id: id, limit: 5 }],
    queryFn: () => fetchCalls({ agent_id: id!, limit: 5, status: "COMPLETED" }),
    enabled: !!id,
  });

  function exportCSV() {
    if (!scorecard) return;
    const rows = [
      ["Agent", "Period (days)", "Avg Speech", "Avg Sales", "Total Calls", "Converted"],
      [
        scorecard.agent_name,
        String(period),
        scorecard.avg_speech_score?.toFixed(1) ?? "",
        scorecard.avg_sales_score?.toFixed(1) ?? "",
        String(scorecard.call_count),
        String(scorecard.disposition_breakdown["CONVERTED"] ?? 0),
      ],
      [],
      ["Week", "Avg Speech", "Avg Sales", "Calls"],
      ...scorecard.score_trend.map((p) => [p.week, p.avg_speech?.toFixed(1) ?? "", p.avg_sales?.toFixed(1) ?? "", String(p.call_count)]),
      [],
      ["Disposition", "Count"],
      ...Object.entries(scorecard.disposition_breakdown).map(([k, v]) => [k, String(v)]),
    ];
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `scorecard_${scorecard.agent_name.replace(/\s+/g, "_")}_${period}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setExportOpen(false);
  }

  function printScorecard() {
    setExportOpen(false);
    setTimeout(() => window.print(), 100);
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-gray-400 text-sm">Loading scorecard…</div>;
  }

  if (isError || !scorecard) {
    return <div className="p-8 text-gray-500 text-sm">Scorecard not available.</div>;
  }

  const trendData = scorecard.score_trend.map((p) => ({
    week: p.week,
    Speech: p.avg_speech,
    Sales: p.avg_sales,
    calls: p.call_count,
  }));

  const dispositionData = Object.entries(scorecard.disposition_breakdown)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([name, count]) => ({ name: name.replace(/_/g, " "), count }));

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-5 transition-colors"
      >
        <ArrowLeft size={14} /> Back
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center">
            <User size={18} className="text-brand-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">{scorecard.agent_name}</h1>
            <p className="text-sm text-gray-500">
              {scorecard.employee_id && <span>{scorecard.employee_id} · </span>}
              {scorecard.team_name ?? "No team"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none"
          >
            {PERIOD_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <div className="relative">
            <button
              onClick={() => setExportOpen((o) => !o)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Download size={13} />
              Export
              <ChevronDown size={12} className={exportOpen ? "rotate-180 transition-transform" : "transition-transform"} />
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-10 py-1">
                <button
                  onClick={exportCSV}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Export CSV
                </button>
                <button
                  onClick={printScorecard}
                  className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Print scorecard
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Score heroes */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <ScoreHero label="Speech Score" value={scorecard.avg_speech_score} />
        <ScoreHero label="Sales Score" value={scorecard.avg_sales_score} />
        <div className="bg-white rounded-xl border border-gray-200 p-5 text-center">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Total Calls</p>
          <p className="text-4xl font-black text-gray-900">{scorecard.call_count}</p>
          <p className="text-xs text-gray-400 mt-0.5">completed</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 text-center">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Converted</p>
          <p className="text-4xl font-black text-emerald-600">
            {scorecard.disposition_breakdown["CONVERTED"] ?? 0}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">calls</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Trend chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Score Trend</h3>
          {trendData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">Not enough data for trend.</p>
          ) : (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                    formatter={(val: number) => val?.toFixed(1)}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="Speech" stroke="#3b82f6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Sales" stroke="#8b5cf6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Disposition breakdown */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">Disposition Breakdown</h3>
          {dispositionData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No disposition data yet.</p>
          ) : (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dispositionData} layout="vertical" margin={{ top: 0, right: 10, bottom: 0, left: 70 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <YAxis dataKey="name" type="category" tick={{ fontSize: 9, fill: "#64748b" }} width={70} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {dispositionData.map((_, i) => (
                      <Cell key={i} fill={i === 0 ? "#10b981" : i === 1 ? "#3b82f6" : "#94a3b8"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      {(scorecard.strengths.length > 0 || scorecard.weaknesses.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-4">
            <h3 className="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <TrendingUp size={13} /> Top Strengths
            </h3>
            <ol className="space-y-1.5">
              {scorecard.strengths.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-emerald-200 text-emerald-800 text-xs font-bold flex items-center justify-center flex-shrink-0">
                    {i + 1}
                  </span>
                  <DimLabel dim={s} />
                </li>
              ))}
            </ol>
          </div>
          <div className="bg-red-50 rounded-xl border border-red-200 p-4">
            <h3 className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <TrendingDown size={13} /> Areas to Improve
            </h3>
            <ol className="space-y-1.5">
              {scorecard.weaknesses.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-red-200 text-red-800 text-xs font-bold flex items-center justify-center flex-shrink-0">
                    {i + 1}
                  </span>
                  <DimLabel dim={s} />
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {/* Recent calls */}
      {recentCalls && recentCalls.data.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <Phone size={13} /> Recent Calls
          </h3>
          <div className="space-y-2">
            {recentCalls.data.map((call) => (
              <Link
                key={call.id}
                to={`/calls/${call.id}`}
                className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-gray-50 transition-colors group"
              >
                <div>
                  <p className="text-sm text-gray-800 font-medium group-hover:text-brand-700">
                    {format(new Date(call.call_date), "dd MMM yyyy")}
                  </p>
                  <p className="text-xs text-gray-500">{call.original_filename}</p>
                </div>
                <div className="flex items-center gap-2">
                  {call.disposition && <DispositionBadge disposition={call.disposition} size="sm" />}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
