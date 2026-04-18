import { useQuery } from "@tanstack/react-query";
import { fetchAgents } from "@/api/agents";
import type { Agent } from "@/types";

export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    select: (res) => res.data as Agent[],
    staleTime: 5 * 60 * 1000,
  });
}
