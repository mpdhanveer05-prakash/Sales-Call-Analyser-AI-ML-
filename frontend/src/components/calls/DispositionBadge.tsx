import { clsx } from "clsx";

const DISPOSITION_META: Record<string, { label: string; color: string }> = {
  CONVERTED:              { label: "Converted",              color: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  INTERESTED_FOLLOWUP:    { label: "Interested — Follow-up", color: "bg-blue-100 text-blue-800 border-blue-300" },
  INTERESTED_NO_NEXTSTEP: { label: "Interested — No Step",  color: "bg-sky-100 text-sky-800 border-sky-300" },
  OBJECTION_PRICE:        { label: "Objection: Price",      color: "bg-orange-100 text-orange-800 border-orange-300" },
  OBJECTION_TIMING:       { label: "Objection: Timing",     color: "bg-orange-100 text-orange-800 border-orange-300" },
  OBJECTION_AUTHORITY:    { label: "Objection: Authority",  color: "bg-orange-100 text-orange-800 border-orange-300" },
  OBJECTION_NEED:         { label: "Objection: Need",       color: "bg-orange-100 text-orange-800 border-orange-300" },
  OBJECTION_COMPETITOR:   { label: "Objection: Competitor", color: "bg-amber-100 text-amber-800 border-amber-300" },
  NOT_INTERESTED:         { label: "Not Interested",        color: "bg-red-100 text-red-800 border-red-300" },
  CALLBACK_REQUESTED:     { label: "Callback Requested",    color: "bg-purple-100 text-purple-800 border-purple-300" },
  VOICEMAIL:              { label: "Voicemail",              color: "bg-gray-100 text-gray-600 border-gray-300" },
  NO_ANSWER:              { label: "No Answer",              color: "bg-gray-100 text-gray-600 border-gray-300" },
  WRONG_NUMBER:           { label: "Wrong Number",           color: "bg-gray-100 text-gray-600 border-gray-300" },
  GATEKEEPER:             { label: "Gatekeeper",             color: "bg-gray-100 text-gray-600 border-gray-300" },
  DNC:                    { label: "Do Not Call",            color: "bg-red-100 text-red-800 border-red-300" },
  PARTIAL_CALL:           { label: "Partial Call",           color: "bg-gray-100 text-gray-600 border-gray-300" },
  LANGUAGE_BARRIER:       { label: "Language Barrier",       color: "bg-gray-100 text-gray-600 border-gray-300" },
  OTHER:                  { label: "Other",                  color: "bg-gray-100 text-gray-600 border-gray-300" },
};

interface Props {
  disposition: string;
  size?: "sm" | "md";
}

export default function DispositionBadge({ disposition, size = "md" }: Props) {
  const meta = DISPOSITION_META[disposition] ?? { label: disposition.replace(/_/g, " "), color: "bg-gray-100 text-gray-600 border-gray-300" };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border font-medium whitespace-nowrap",
        meta.color,
        size === "sm" ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1",
      )}
    >
      {meta.label}
    </span>
  );
}
