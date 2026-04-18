import { Lightbulb, Clock, TrendingUp } from "lucide-react";
import type { Summary } from "@/types";

interface Props {
  summary: Summary;
}

export default function SummaryCard({ summary }: Props) {
  return (
    <div className="space-y-6">
      {/* Executive summary */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">
          Call Summary
        </h3>
        <p className="text-gray-800 text-sm leading-relaxed bg-gray-50 rounded-xl p-4 border border-gray-200">
          {summary.executive_summary}
        </p>
      </div>

      {/* Key moments */}
      {summary.key_moments.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Clock size={13} /> Key Moments
          </h3>
          <ul className="space-y-1.5">
            {summary.key_moments.map((moment, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                {moment}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Coaching suggestions */}
      {summary.coaching_suggestions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2 flex items-center gap-1.5">
            <Lightbulb size={13} className="text-amber-500" /> Coaching Suggestions
          </h3>
          <ol className="space-y-2">
            {summary.coaching_suggestions.map((suggestion, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                <span className="shrink-0 w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                {suggestion}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* LLM reasoning */}
      {summary.disposition_reasoning && (
        <div className="text-xs text-gray-400 border-t border-gray-100 pt-3">
          <span className="font-medium text-gray-500">Disposition reasoning: </span>
          {summary.disposition_reasoning}
          {summary.disposition_confidence != null && (
            <span className="ml-1">({(summary.disposition_confidence * 100).toFixed(0)}% confidence)</span>
          )}
        </div>
      )}
    </div>
  );
}
