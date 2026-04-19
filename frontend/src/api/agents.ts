import apiClient from "./client";
import type { Agent, AgentScorecard, PaginatedResponse } from "@/types";

export async function fetchAgents(): Promise<PaginatedResponse<Agent>> {
  const { data } = await apiClient.get<PaginatedResponse<Agent>>("/agents");
  return data;
}

export async function fetchAgentScorecard(agentId: string, period = 30): Promise<AgentScorecard> {
  const { data } = await apiClient.get<AgentScorecard>(`/agents/${agentId}/scorecard`, { params: { period } });
  return data;
}
