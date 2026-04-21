import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Users, RefreshCw } from "lucide-react";
import { fetchAgents, compareAgents } from "@/api/agents";
import type { AgentScorecard } from "@/types";

function ScoreBar({ value, max = 100 }: { value: number | null; max?: number }) {
  if (value === null) return <span className="text-gray-400 text-sm">—</span>;
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${value >= 80 ? "bg-emerald-500" : value >= 60 ? "bg-yellow-400" : "bg-red-400"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-medium text-gray-800 w-9 text-right">{value.toFixed(0)}</span>
    </div>
  );
}

function ScorecardColumn({ card, side }: { card: AgentScorecard; side: "a" | "b" }) {
  const color = side === "a" ? "blue" : "violet";
  return (
    <div className="flex-1 min-w-0">
      <div className={`rounded-xl p-4 mb-4 bg-${color}-50 border border-${color}-100`}>
        <p className="text-xs text-gray-500 uppercase tracking-wide">Agent</p>
        <p className="text-lg font-bold text-gray-900">{card.agent_name}</p>
        {card.team_name && <p className="text-xs text-gray-500">{card.team_name}</p>}
      </div>

      <div className="space-y-3">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Overview</p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Calls</span>
              <span className="font-bold text-gray-900">{card.call_count}</span>
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-gray-600">Speech Score</span>
              </div>
              <ScoreBar value={card.avg_speech_score} />
            </div>
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-gray-600">Sales Score</span>
              </div>
              <ScoreBar value={card.avg_sales_score} />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Strengths</p>
          {card.strengths.length > 0 ? (
            <ul className="space-y-1">
              {card.strengths.map((s) => (
                <li key={s} className="text-xs flex items-center gap-1.5 text-emerald-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                  {s.replace("speech:", "Speech · ").replace("sales:", "Sales · ")}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400">Not enough data</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Areas to Improve</p>
          {card.weaknesses.length > 0 ? (
            <ul className="space-y-1">
              {card.weaknesses.map((w) => (
                <li key={w} className="text-xs flex items-center gap-1.5 text-red-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                  {w.replace("speech:", "Speech · ").replace("sales:", "Sales · ")}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-gray-400">Not enough data</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Dispositions</p>
          {Object.keys(card.disposition_breakdown).length > 0 ? (
            <div className="space-y-1">
              {Object.entries(card.disposition_breakdown)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 5)
                .map(([disp, count]) => (
                  <div key={disp} className="flex justify-between text-xs">
                    <span className="text-gray-600 truncate max-w-[140px]">{disp.replace(/_/g, " ")}</span>
                    <span className="font-medium text-gray-800">{count}</span>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">No completed calls</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AgentComparePage() {
  const [agentA, setAgentA] = useState("");
  const [agentB, setAgentB] = useState("");
  const [period, setPeriod] = useState(30);

  const { data: agentsData } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });
  const agents = agentsData?.data ?? [];

  const enabled = !!agentA && !!agentB && agentA !== agentB;

  const { data: comparison, isLoading, refetch } = useQuery({
    queryKey: ["compare-agents", agentA, agentB, period],
    queryFn: () => compareAgents(agentA, agentB, period),
    enabled,
  });

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users size={20} /> Agent Comparison
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Compare performance side-by-side</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3 mb-6 bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Agent A</label>
          <select
            value={agentA}
            onChange={(e) => setAgentA(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.full_name}</option>
            ))}
          </select>
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs font-medium text-gray-600 mb-1">Agent B</label>
          <select
            value={agentB}
            onChange={(e) => setAgentB(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select agent…</option>
            {agents.filter((a) => a.id !== agentA).map((a) => (
              <option key={a.id} value={a.id}>{a.full_name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Period</label>
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
          </select>
        </div>
        {comparison && (
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        )}
      </div>

      {/* Results */}
      {!agentA || !agentB ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Users size={36} className="mb-3 opacity-40" />
          <p className="text-sm font-medium">Select two agents to compare</p>
        </div>
      ) : agentA === agentB ? (
        <div className="text-center py-10 text-sm text-amber-600 bg-amber-50 rounded-xl border border-amber-200">
          Please select two different agents.
        </div>
      ) : isLoading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <RefreshCw size={20} className="animate-spin mr-2" /> Loading comparison…
        </div>
      ) : comparison ? (
        <div className="flex gap-6">
          <ScorecardColumn card={comparison.agent_a} side="a" />
          <div className="flex flex-col items-center justify-center gap-2 flex-shrink-0">
            <div className="w-px flex-1 bg-gray-200" />
            <span className="text-xs font-bold text-gray-400 bg-white px-1">VS</span>
            <div className="w-px flex-1 bg-gray-200" />
          </div>
          <ScorecardColumn card={comparison.agent_b} side="b" />
        </div>
      ) : null}
    </div>
  );
}
