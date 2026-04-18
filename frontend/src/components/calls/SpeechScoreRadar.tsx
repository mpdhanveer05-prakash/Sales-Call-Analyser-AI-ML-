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
import type { SpeechScore } from "@/types";

interface Props {
  score: SpeechScore;
}

const DIMENSIONS = [
  { key: "pronunciation", label: "Pronunciation", weight: "15%", description: "Word clarity based on Whisper confidence" },
  { key: "intonation",    label: "Intonation",    weight: "15%", description: "Pitch variance — monotone vs expressive" },
  { key: "fluency",       label: "Fluency",        weight: "15%", description: "Natural pacing with appropriate pauses" },
  { key: "grammar",       label: "Grammar",        weight: "15%", description: "Errors per 100 words (LanguageTool)" },
  { key: "vocabulary",    label: "Vocabulary",     weight: "10%", description: "Lexical diversity (type-token ratio)" },
  { key: "pace",          label: "Pace",           weight: "10%", description: "Words per minute (target: 120–160)" },
  { key: "clarity",       label: "Clarity",        weight: "10%", description: "Proportion of clearly spoken words" },
  { key: "filler_score",  label: "Filler Words",   weight: "10%", description: "Penalty for um, uh, like, basically…" },
] as const;

function scoreColor(val: number): string {
  if (val >= 80) return "text-emerald-600";
  if (val >= 60) return "text-yellow-600";
  if (val >= 40) return "text-orange-500";
  return "text-red-600";
}

function scoreBg(val: number): string {
  if (val >= 80) return "bg-emerald-50 border-emerald-200";
  if (val >= 60) return "bg-yellow-50 border-yellow-200";
  if (val >= 40) return "bg-orange-50 border-orange-200";
  return "bg-red-50 border-red-200";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const { subject, value } = payload[0].payload;
  const dim = DIMENSIONS.find((d) => d.label === subject);
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-md px-3 py-2 text-xs max-w-[180px]">
      <p className="font-semibold text-gray-800 mb-0.5">{subject}</p>
      <p className={clsx("text-lg font-bold", scoreColor(value))}>{value.toFixed(0)}</p>
      {dim && <p className="text-gray-500 leading-tight mt-1">{dim.description}</p>}
    </div>
  );
}

export default function SpeechScoreRadar({ score }: Props) {
  const chartData = DIMENSIONS.map((d) => ({
    subject: d.label,
    value: score[d.key as keyof SpeechScore] as number,
    fullMark: 100,
  }));

  return (
    <div className="space-y-6">
      {/* Composite score hero */}
      <div className="flex items-center gap-4">
        <div className="text-center">
          <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">Speech Quality</p>
          <p className={clsx("text-5xl font-black", scoreColor(score.composite))}>
            {score.composite.toFixed(0)}
          </p>
          <p className="text-xs text-gray-400 mt-1">out of 100</p>
        </div>

        {/* Quick-stats */}
        <div className="flex gap-3 flex-wrap ml-4">
          {score.pace_wpm != null && (
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-gray-500">Pace</p>
              <p className="text-base font-bold text-gray-800">{score.pace_wpm.toFixed(0)} WPM</p>
            </div>
          )}
          {score.fillers_per_min != null && (
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-gray-500">Fillers/min</p>
              <p className="text-base font-bold text-gray-800">{score.fillers_per_min.toFixed(1)}</p>
            </div>
          )}
          {score.talk_ratio != null && (
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-gray-500">Talk ratio</p>
              <p className="text-base font-bold text-gray-800">{(score.talk_ratio * 100).toFixed(0)}%</p>
            </div>
          )}
        </div>
      </div>

      {/* Radar chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: "#64748b" }} />
            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
            <Radar
              name="Score"
              dataKey="value"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.2}
              strokeWidth={2}
            />
            <Tooltip content={<CustomTooltip />} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Dimension breakdown table */}
      <div className="grid grid-cols-2 gap-2">
        {DIMENSIONS.map((d) => {
          const val = score[d.key as keyof SpeechScore] as number;
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

      {/* Score legend */}
      <div className="flex gap-4 text-[10px] text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> 80–100 Excellent</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500" /> 60–79 Good</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500" /> 40–59 Fair</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> 0–39 Needs Work</span>
      </div>
    </div>
  );
}
