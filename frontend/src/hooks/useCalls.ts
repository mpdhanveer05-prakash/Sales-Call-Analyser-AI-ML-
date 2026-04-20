import { useQuery } from "@tanstack/react-query";
import { fetchCalls, type CallFilters } from "@/api/calls";
import type { CallStatus } from "@/types";

const PROCESSING_STATUSES: CallStatus[] = ["QUEUED", "TRANSCRIBING", "ANALYZING", "SCORING"];

export function useCalls(filters: CallFilters = {}) {
  const { data, ...rest } = useQuery({
    queryKey: ["calls", filters],
    queryFn: () => fetchCalls(filters),
    refetchInterval: (query) => {
      const calls = query.state.data?.data ?? [];
      const hasActive = calls.some((c) => PROCESSING_STATUSES.includes(c.status));
      return hasActive ? 5_000 : false;
    },
  });

  return { data, ...rest };
}
