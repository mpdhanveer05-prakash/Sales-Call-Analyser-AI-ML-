import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { clsx } from "clsx";
import type { SalesScore } from "@/types";

interface Props {
  score: SalesScore;
}

const DIMENSIONS = [
  { key: "greeting",          label: "Greeting",         weight: "10%", description: "Professional opener, name and company stated" },
  { key: "rapport",           label: "Rapport",           weight: "10%", description: "Personalisation and active listening" },
  { key: "discovery",         label: "Discovery",         weight: "15%", description: "Open-ended questions, need exploration" },
  { key: "value_explanation", label: "Value",             weight: "20%", description: "Benefit articulation tied to prospect's need" },
  { key: "objection_handling",label: "Objections",        weight: "20%", description: "Acknowledge → address → confirm" },
  { key: "script_adherence",  label: "Script",            weight: "10%", description: "Coverage of required talking points" },
  { key: "closing",           label: "Closing",           weight: "10%", description: "Explicit ask, agreed next action" },
  { key: "compliance",        label: "Compliance",        weight: "5%",  description: "Required disclosures and no prohibited phrases" },
] as const;

function scoreColor(v: number) {
  if (v >= 80) return "text-emerald-600";
  if (v >= 60) return "text-yellow-600";
  if (v >= 40) return "text-orange-500";
  return "text-red-600";
}
function scoreBg(v: number) {
  if (v >= 80) return "bg-emerald-50 border-emerald-200";
  if (v >= 60) return "bg-yellow-50 border-yellow-200";
  if (v >= 40) return "bg-orange-50 border-orange-200";
  return "bg-red-50 border-red-200";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const { subject, value } = payload[0].payload;
  const dim = DIMENSIONS.find((d) => d.label === subject);
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-3 py-2 text-xs max-w-[200px]">
      <p className="font-semibold text-gray-800 mb-0.5">{subject}</p>
      <p className={clsx("text-lg font-bold", scoreColor(value))}>{value.toFixed(0)}</p>
      {dim && <p className="text-gray-500 leading-tight mt-1">{dim.description}</p>}
    </div>
  );
}

export default function SalesScoreRadar({ score }: Props) {
  const chartData = DIMENSIONS.map((d) => ({
    subject: d.label,
    value: score[d.key as keyof SalesScore] as number,
    fullMark: 100,
  }));

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="flex items-center gap-4">
        <div className="text-center">
          <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">Sales Quality</p>
          <p className={clsx("text-5xl font-black", scoreColor(score.composite))}>
            {score.composite.toFixed(0)}
          </p>
          <p className="text-xs text-gray-400 mt-1">out of 100</p>
        </div>
      </div>

      {/* Radar */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "#64748b" }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
            <Radar
              name="Score"
              dataKey="value"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.2}
              strokeWidth={2}
            />
            <Tooltip content={<CustomTooltip />} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-2 gap-2">
        {DIMENSIONS.map((d) => {
          const val = score[d.key as keyof SalesScore] as number;
          return (
            <div key={d.key} className={clsx("rounded-lg border px-3 py-2 flex items-center justify-between", scoreBg(val))}>
              <div>
                <p className="text-xs font-medium text-gray-700">{d.label}</p>
                <p className="text-[10px] text-gray-400">{d.weight} weight</p>
              </div>
              <span className={clsx("text-lg font-bold", scoreColor(val))}>{val.toFixed(0)}</span>
            </div>
          );
        })}
      </div>

      {/* LLM justifications accordion */}
      {score.details && (
        <details className="text-sm">
          <summary className="cursor-pointer text-gray-500 hover:text-gray-700 select-none">
            Show LLM justifications ↓
          </summary>
          <div className="mt-3 space-y-3">
            {DIMENSIONS.map((d) => {
              const detail = (score.details as Record<string, { score: number; justification: string; quote: string }>)[d.key];
              if (!detail) return null;
              return (
                <div key={d.key} className="bg-gray-50 rounded-lg p-3">
                  <p className="font-medium text-gray-800 text-xs mb-1">{d.label} — {detail.score}/10</p>
                  <p className="text-gray-600 text-xs">{detail.justification}</p>
                  {detail.quote && (
                    <blockquote className="mt-1.5 pl-2 border-l-2 border-gray-300 text-gray-500 italic text-xs">
                      "{detail.quote}"
                    </blockquote>
                  )}
                </div>
              );
            })}
          </div>
        </details>
      )}

      <div className="flex gap-4 text-[10px] text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> 80–100 Excellent</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> 60–79 Good</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> 40–59 Fair</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> 0–39 Needs Work</span>
      </div>
    </div>
  );
}
