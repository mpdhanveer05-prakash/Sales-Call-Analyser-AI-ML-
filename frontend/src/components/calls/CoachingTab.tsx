import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play, CheckCircle, Circle, Lightbulb, AlertTriangle } from "lucide-react";
import { clsx } from "clsx";
import { resolveObjection } from "@/api/calls";
import type { CoachingClip, Objection } from "@/types";

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  greeting:           { label: "Greeting",         color: "bg-blue-100 text-blue-800 border-blue-200" },
  rapport:            { label: "Rapport",           color: "bg-sky-100 text-sky-800 border-sky-200" },
  discovery:          { label: "Discovery",         color: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  value_proposition:  { label: "Value Prop",        color: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  objection_handling: { label: "Objection",         color: "bg-orange-100 text-orange-800 border-orange-200" },
  closing:            { label: "Closing",           color: "bg-purple-100 text-purple-800 border-purple-200" },
  compliance:         { label: "Compliance",        color: "bg-red-100 text-red-800 border-red-200" },
  missed_opportunity: { label: "Missed Opp.",       color: "bg-amber-100 text-amber-800 border-amber-200" },
};

const OBJECTION_META: Record<string, { label: string; color: string }> = {
  PRICE:      { label: "Price",      color: "bg-orange-100 text-orange-800 border-orange-200" },
  TIMING:     { label: "Timing",     color: "bg-amber-100 text-amber-800 border-amber-200" },
  AUTHORITY:  { label: "Authority",  color: "bg-yellow-100 text-yellow-800 border-yellow-200" },
  NEED:       { label: "Need",       color: "bg-red-100 text-red-800 border-red-200" },
  COMPETITOR: { label: "Competitor", color: "bg-pink-100 text-pink-800 border-pink-200" },
  OTHER:      { label: "Other",      color: "bg-gray-100 text-gray-600 border-gray-200" },
};

function msToTime(ms: number): string {
  const totalSecs = Math.floor(ms / 1000);
  const m = Math.floor(totalSecs / 60);
  const s = totalSecs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface Props {
  callId: string;
  clips: CoachingClip[];
  objections: Objection[];
  onSeek: (ms: number) => void;
}

export default function CoachingTab({ callId, clips, objections, onSeek }: Props) {
  const qc = useQueryClient();

  const resolveMutation = useMutation({
    mutationFn: (objectionId: string) => resolveObjection(callId, objectionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["coaching", callId] }),
  });

  const hasClips = clips.length > 0;
  const hasObjections = objections.length > 0;

  if (!hasClips && !hasObjections) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 flex flex-col items-center gap-3 text-gray-400">
        <Lightbulb size={28} className="opacity-40" />
        <p className="text-sm">No coaching moments or objections extracted for this call.</p>
        <p className="text-xs text-gray-400">This is populated automatically after the call is processed.</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Coaching Moments */}
      {hasClips && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Lightbulb size={14} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Coaching Moments
            </h3>
            <span className="ml-auto text-xs text-gray-400">{clips.length} moment{clips.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="divide-y divide-gray-50">
            {clips.map((clip) => {
              const meta = CATEGORY_META[clip.category] ?? { label: clip.category, color: "bg-gray-100 text-gray-600 border-gray-200" };
              return (
                <div key={clip.id} className="px-5 py-4 flex items-start gap-3">
                  <button
                    onClick={() => onSeek(clip.start_ms)}
                    title={`Jump to ${msToTime(clip.start_ms)}`}
                    className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-full bg-brand-50 border border-brand-200 text-brand-600 hover:bg-brand-100 flex items-center justify-center transition-colors"
                  >
                    <Play size={12} fill="currentColor" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={clsx(
                          "inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border",
                          meta.color
                        )}
                      >
                        {meta.label}
                      </span>
                      <span className="text-xs text-gray-400">
                        {msToTime(clip.start_ms)} – {msToTime(clip.end_ms)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed">{clip.reason}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Objections */}
      {hasObjections && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <AlertTriangle size={14} className="text-orange-500" />
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Customer Objections
            </h3>
            <span className="ml-auto text-xs text-gray-400">
              {objections.filter((o) => o.resolved).length}/{objections.length} resolved
            </span>
          </div>
          <div className="divide-y divide-gray-50">
            {objections.map((obj) => {
              const meta = OBJECTION_META[obj.objection_type] ?? OBJECTION_META["OTHER"];
              return (
                <div
                  key={obj.id}
                  className={clsx("px-5 py-4 flex items-start gap-3 transition-colors", obj.resolved && "bg-gray-50/60")}
                >
                  <button
                    onClick={() => onSeek(obj.timestamp_ms)}
                    title={`Jump to ${msToTime(obj.timestamp_ms)}`}
                    className="mt-0.5 flex-shrink-0 w-8 h-8 rounded-full bg-orange-50 border border-orange-200 text-orange-600 hover:bg-orange-100 flex items-center justify-center transition-colors"
                  >
                    <Play size={12} fill="currentColor" />
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className={clsx(
                          "inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border",
                          meta.color
                        )}
                      >
                        {meta.label}
                      </span>
                      <span className="text-xs text-gray-400">{msToTime(obj.timestamp_ms)}</span>
                    </div>
                    <blockquote className="pl-2 border-l-2 border-gray-300 text-sm text-gray-600 italic leading-relaxed mb-2">
                      "{obj.quote}"
                    </blockquote>
                    <button
                      onClick={() => resolveMutation.mutate(obj.id)}
                      disabled={resolveMutation.isPending}
                      className={clsx(
                        "flex items-center gap-1.5 text-xs font-medium transition-colors",
                        obj.resolved
                          ? "text-emerald-600 hover:text-emerald-700"
                          : "text-gray-400 hover:text-gray-600"
                      )}
                    >
                      {obj.resolved
                        ? <><CheckCircle size={12} /> Resolved</>
                        : <><Circle size={12} /> Mark resolved</>}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
