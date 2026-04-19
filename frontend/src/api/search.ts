import apiClient from "./client";
import type { SearchResult } from "@/types";

export interface SearchParams {
  query: string;
  search_type?: "keyword" | "semantic";
  agent_id?: string;
  date_from?: string;
  date_to?: string;
  disposition?: string;
  limit?: number;
}

export async function searchCalls(params: SearchParams): Promise<SearchResult[]> {
  const { data } = await apiClient.post<SearchResult[]>("/search", params);
  return data;
}
