import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock } from "lucide-react";
import { fetchCall } from "@/api/calls";
import { StatusBadge } from "@/components/ui/badge";
import { format } from "date-fns";
import type { CallStatus } from "@/types";

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: call, isLoading } = useQuery({
    queryKey: ["call", id],
    queryFn: () => fetchCall(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Loading call…
      </div>
    );
  }

  if (!call) {
    return (
      <div className="p-8 text-gray-500 text-sm">Call not found.</div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <button
        onClick={() => navigate("/calls")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6 transition-colors"
      >
        <ArrowLeft size={14} />
        Back to calls
      </button>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{call.original_filename}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {call.agent_name} · {format(new Date(call.call_date), "dd MMM yyyy")}
          </p>
        </div>
        <StatusBadge status={call.status as CallStatus} />
      </div>

      {/* Metadata cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Speech Score", value: call.speech_score?.toFixed(0) ?? "—" },
          { label: "Sales Score", value: call.sales_score?.toFixed(0) ?? "—" },
          { label: "Duration", value: call.duration_seconds ? `${Math.floor(call.duration_seconds / 60)}m ${call.duration_seconds % 60}s` : "—" },
          { label: "Disposition", value: call.disposition ?? "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
            <p className="text-xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Transcript / scores (Phase 2+) */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 text-gray-400 text-sm">
          <Clock size={16} />
          <span>Transcript and score details will be available after Phase 2 is built.</span>
        </div>
      </div>
    </div>
  );
}
