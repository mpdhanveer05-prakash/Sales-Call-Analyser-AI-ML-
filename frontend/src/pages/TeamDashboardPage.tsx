import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, Award, BarChart2, RefreshCw } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { fetchTeamDashboard } from "@/api/dashboard";
import DispositionBadge from "@/components/calls/DispositionBadge";

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

function MetricCard({ label, value, sub, color = "text-gray-900" }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-3xl font-black ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function TeamDashboardPage() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState(30);

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["team-dashboard", period],
    queryFn: () => fetchTeamDashboard(period),
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        <RefreshCw size={16} className="animate-spin mr-2" /> Loading dashboard…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8">
        <p className="text-sm text-red-600">Failed to load dashboard. Ensure the backend is running.</p>
      </div>
    );
  }

  const trendData = data.weekly_trend.map((p) => ({
    week: p.week,
    Speech: p.avg_speech,
    Sales: p.avg_sales,
    Calls: p.call_count,
  }));

  const topDispositions = Object.entries(data.disposition_breakdown)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([name, count]) => ({ name, count }));

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Team Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Team-wide performance overview</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
          </button>
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none"
          >
            {PERIOD_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <MetricCard
          label="Total Calls"
          value={String(data.total_calls)}
          sub="completed"
          color="text-gray-900"
        />
        <MetricCard
          label="Avg Speech Score"
          value={data.avg_speech_score !== null ? data.avg_speech_score.toFixed(1) : "—"}
          sub="out of 100"
          color={scoreColor(data.avg_speech_score)}
        />
        <MetricCard
          label="Avg Sales Score"
          value={data.avg_sales_score !== null ? data.avg_sales_score.toFixed(1) : "—"}
          sub="out of 100"
          color={scoreColor(data.avg_sales_score)}
        />
        <MetricCard
          label="Conversion Rate"
          value={data.conversion_rate !== null ? `${(data.conversion_rate * 100).toFixed(1)}%` : "—"}
          sub="of completed calls"
          color={data.conversion_rate !== null && data.conversion_rate >= 0.1 ? "text-emerald-600" : "text-gray-900"}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Weekly trend */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <TrendingUp size={13} /> Weekly Score Trend
          </h3>
          {trendData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">No data for the selected period.</p>
          ) : (
            <div className="h-56">
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

        {/* Disposition distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <BarChart2 size={13} /> Disposition Breakdown
          </h3>
          {topDispositions.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-10">No disposition data yet.</p>
          ) : (
            <div className="space-y-2">
              {topDispositions.slice(0, 6).map(({ name, count }) => (
                <div key={name} className="flex items-center gap-2">
                  <DispositionBadge disposition={name} size="sm" />
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-400 rounded-full"
                      style={{ width: `${Math.min(100, (count / data.total_calls) * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-gray-700 w-6 text-right">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Leaderboard */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-1.5">
          <Award size={15} className="text-amber-500" />
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Leaderboard</h3>
        </div>
        {data.leaderboard.length === 0 ? (
          <div className="py-12 text-center text-sm text-gray-400">No completed calls in this period.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-10">#</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Calls</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Speech</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Sales</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Composite</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.leaderboard.map((entry) => (
                <tr
                  key={entry.agent_id}
                  onClick={() => navigate(`/agents/${entry.agent_id}`)}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                >
                  <td className="px-5 py-3.5">
                    {entry.rank <= 3 ? (
                      <span className={`text-base ${entry.rank === 1 ? "text-amber-400" : entry.rank === 2 ? "text-gray-400" : "text-amber-700"}`}>
                        {entry.rank === 1 ? "🥇" : entry.rank === 2 ? "🥈" : "🥉"}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">{entry.rank}</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 font-medium text-gray-900">{entry.agent_name}</td>
                  <td className="px-5 py-3.5 text-right text-gray-600">{entry.call_count}</td>
                  <td className={`px-5 py-3.5 text-right font-semibold ${scoreColor(entry.avg_speech_score)}`}>
                    {entry.avg_speech_score?.toFixed(1) ?? "—"}
                  </td>
                  <td className={`px-5 py-3.5 text-right font-semibold ${scoreColor(entry.avg_sales_score)}`}>
                    {entry.avg_sales_score?.toFixed(1) ?? "—"}
                  </td>
                  <td className={`px-5 py-3.5 text-right font-bold text-base ${scoreColor(entry.composite_score)}`}>
                    {entry.composite_score?.toFixed(1) ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
