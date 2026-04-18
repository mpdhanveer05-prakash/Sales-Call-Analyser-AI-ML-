import apiClient from "./client";
import type { Agent, PaginatedResponse } from "@/types";

export async function fetchAgents(): Promise<PaginatedResponse<Agent>> {
  const { data } = await apiClient.get<PaginatedResponse<Agent>>("/agents");
  return data;
}
