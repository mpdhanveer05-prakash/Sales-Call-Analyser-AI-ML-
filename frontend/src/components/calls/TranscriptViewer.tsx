import { useRef, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { clsx } from "clsx";
import type { TranscriptSegment, SpeakerRole } from "@/types";

interface Props {
  segments: TranscriptSegment[];
  currentTimeMs: number;
  onSeek: (ms: number) => void;
}

function formatTimestamp(ms: number): string {
  const totalSecs = Math.floor(ms / 1000);
  const m = Math.floor(totalSecs / 60);
  const s = totalSecs % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ─── Role display config ────────────────────────────────────────────────────
const ROLE_STYLES: Record<
  SpeakerRole,
  { label: string; dot: string; text: string; chip: string; italic?: boolean }
> = {
  HUMAN_AGENT: {
    label: "AGENT",
    dot: "bg-blue-500",
    text: "text-blue-600",
    chip: "bg-blue-50 border-blue-200",
  },
  HUMAN_CUSTOMER: {
    label: "CUSTOMER",
    dot: "bg-emerald-500",
    text: "text-emerald-600",
    chip: "bg-emerald-50 border-emerald-200",
  },
  AUTO_ATTENDANT: {
    label: "AUTO-ATTENDANT",
    dot: "bg-slate-400",
    text: "text-slate-500",
    chip: "bg-slate-50 border-slate-200",
    italic: true,
  },
  IVR_SYSTEM: {
    label: "IVR",
    dot: "bg-slate-400",
    text: "text-slate-500",
    chip: "bg-slate-50 border-slate-200",
    italic: true,
  },
  VOICEMAIL_GREETING: {
    label: "VOICEMAIL",
    dot: "bg-slate-400",
    text: "text-slate-500",
    chip: "bg-slate-50 border-slate-200",
    italic: true,
  },
  VOICEMAIL_MENU: {
    label: "VM MENU",
    dot: "bg-slate-400",
    text: "text-slate-500",
    chip: "bg-slate-50 border-slate-200",
    italic: true,
  },
  UNKNOWN: {
    label: "UNKNOWN",
    dot: "bg-rose-400",
    text: "text-rose-600",
    chip: "bg-rose-50 border-rose-200",
  },
};

function getRole(seg: TranscriptSegment): SpeakerRole {
  if (seg.role) return seg.role;
  // Back-compat for old data without role: map speaker
  if (seg.speaker === "AGENT") return "HUMAN_AGENT";
  if (seg.speaker === "CUSTOMER") return "HUMAN_CUSTOMER";
  if (seg.speaker === "SYSTEM") return "AUTO_ATTENDANT";
  return "UNKNOWN";
}

export default function TranscriptViewer({ segments, currentTimeMs, onSeek }: Props) {
  const [query, setQuery] = useState("");
  const [showAutomated, setShowAutomated] = useState(true);
  const activeRef = useRef<HTMLDivElement>(null);

  let activeIdx = -1;
  for (let i = segments.length - 1; i >= 0; i--) {
    if (currentTimeMs >= segments[i].start_ms && currentTimeMs < segments[i].end_ms) {
      activeIdx = i;
      break;
    }
  }

  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeIdx]);

  let displayed = segments;
  if (!showAutomated) {
    displayed = displayed.filter((s) => {
      const r = getRole(s);
      return r === "HUMAN_AGENT" || r === "HUMAN_CUSTOMER";
    });
  }
  if (query.trim()) {
    displayed = displayed.filter((s) =>
      s.text.toLowerCase().includes(query.toLowerCase())
    );
  }

  const highlight = (text: string) => {
    if (!query.trim()) return text;
    const regex = new RegExp(
      `(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
      "gi"
    );
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-200 rounded-sm px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const hasAutomated = segments.some((s) => {
    const r = getRole(s);
    return r !== "HUMAN_AGENT" && r !== "HUMAN_CUSTOMER" && r !== "UNKNOWN";
  });

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="relative mb-3">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search transcript…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {query && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">
            {displayed.length} result{displayed.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Legend + filter toggle */}
      <div className="flex items-center justify-between mb-3 text-xs text-gray-500">
        <div className="flex gap-3 flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Agent
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Customer
          </span>
          {hasAutomated && (
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" /> Automated
            </span>
          )}
        </div>
        {hasAutomated && (
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showAutomated}
              onChange={(e) => setShowAutomated(e.target.checked)}
              className="rounded border-gray-300"
            />
            Show automated
          </label>
        )}
      </div>

      {/* Segments */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {displayed.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No matching segments.</p>
        ) : (
          displayed.map((seg) => {
            const role = getRole(seg);
            const style = ROLE_STYLES[role];
            const isActive = !query && segments.indexOf(seg) === activeIdx;
            const lowConfidence =
              seg.role_confidence != null && seg.role_confidence < 0.7;

            return (
              <div
                key={seg.id}
                ref={isActive ? activeRef : undefined}
                onClick={() => onSeek(seg.start_ms)}
                className={clsx(
                  "group flex gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors",
                  isActive
                    ? "bg-blue-50 border border-blue-200"
                    : `hover:${style.chip} border border-transparent`
                )}
              >
                {/* Timestamp */}
                <span className="shrink-0 text-xs text-gray-400 tabular-nums w-10 pt-0.5">
                  {formatTimestamp(seg.start_ms)}
                </span>

                {/* Role dot */}
                <span
                  className={clsx("shrink-0 w-2 h-2 rounded-full mt-1.5", style.dot)}
                />

                {/* Role label + text */}
                <div className="flex-1 min-w-0">
                  <span
                    className={clsx(
                      "text-[10px] font-semibold uppercase tracking-wider mr-1",
                      style.text
                    )}
                  >
                    {style.label}
                  </span>
                  {lowConfidence && (
                    <span className="text-[9px] text-rose-500 mr-1" title="Low role confidence">
                      ⚠
                    </span>
                  )}
                  <span
                    className={clsx(
                      "text-sm leading-relaxed",
                      style.italic ? "text-gray-500 italic" : "text-gray-800"
                    )}
                  >
                    {highlight(seg.text)}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
