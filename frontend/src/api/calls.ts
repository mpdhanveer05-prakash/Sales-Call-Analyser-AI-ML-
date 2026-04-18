import apiClient from "./client";
import type { Call, PaginatedResponse } from "@/types";

export interface CallFilters {
  page?: number;
  limit?: number;
  agent_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
}

export async function fetchCalls(filters: CallFilters = {}): Promise<PaginatedResponse<Call>> {
  const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== ""));
  const { data } = await apiClient.get<PaginatedResponse<Call>>("/calls", { params });
  return data;
}

export async function fetchCall(id: string): Promise<Call> {
  const { data } = await apiClient.get<Call>(`/calls/${id}`);
  return data;
}

export async function uploadCall(formData: FormData): Promise<{ id: string; status: string }> {
  const { data } = await apiClient.post("/calls/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
