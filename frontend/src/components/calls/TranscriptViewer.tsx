import { useRef, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { clsx } from "clsx";
import type { TranscriptSegment } from "@/types";

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

export default function TranscriptViewer({ segments, currentTimeMs, onSeek }: Props) {
  const [query, setQuery] = useState("");
  const activeRef = useRef<HTMLDivElement>(null);

  let activeIdx = -1;
  for (let i = segments.length - 1; i >= 0; i--) {
    if (currentTimeMs >= segments[i].start_ms && currentTimeMs < segments[i].end_ms) {
      activeIdx = i;
      break;
    }
  }

  // Auto-scroll to active segment
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeIdx]);

  const filtered = query.trim()
    ? segments.filter((s) => s.text.toLowerCase().includes(query.toLowerCase()))
    : segments;

  const highlight = (text: string) => {
    if (!query.trim()) return text;
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
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
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Speaker legend */}
      <div className="flex gap-4 mb-3 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> AGENT
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> CUSTOMER
        </span>
      </div>

      {/* Segments */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {filtered.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No matching segments.</p>
        ) : (
          filtered.map((seg, idx) => {
            const isActive = !query && idx === activeIdx;
            const isAgent = seg.speaker === "AGENT";

            return (
              <div
                key={seg.id}
                ref={isActive ? activeRef : undefined}
                onClick={() => onSeek(seg.start_ms)}
                className={clsx(
                  "group flex gap-3 rounded-lg px-3 py-2 cursor-pointer transition-colors",
                  isActive
                    ? "bg-blue-50 border border-blue-200"
                    : "hover:bg-gray-50 border border-transparent"
                )}
              >
                {/* Timestamp */}
                <span className="shrink-0 text-xs text-gray-400 tabular-nums w-10 pt-0.5">
                  {formatTimestamp(seg.start_ms)}
                </span>

                {/* Speaker dot */}
                <span
                  className={clsx(
                    "shrink-0 w-2 h-2 rounded-full mt-1.5",
                    isAgent ? "bg-blue-500" : "bg-emerald-500"
                  )}
                />

                {/* Speaker label + text */}
                <div className="flex-1 min-w-0">
                  <span
                    className={clsx(
                      "text-[10px] font-semibold uppercase tracking-wider mr-1",
                      isAgent ? "text-blue-600" : "text-emerald-600"
                    )}
                  >
                    {seg.speaker}
                  </span>
                  <span className="text-sm text-gray-800 leading-relaxed">
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
