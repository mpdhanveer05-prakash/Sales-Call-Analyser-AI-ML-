import apiClient from "./client";
import type { Call, PaginatedResponse, Transcript, CallScores, Summary, CoachingData } from "@/types";

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

export async function fetchTranscript(callId: string): Promise<Transcript> {
  const { data } = await apiClient.get<Transcript>(`/calls/${callId}/transcript`);
  return data;
}

export async function fetchAudioUrl(callId: string): Promise<string> {
  const { data } = await apiClient.get<{ url: string }>(`/calls/${callId}/audio-url`);
  return data.url;
}

export async function fetchScores(callId: string): Promise<CallScores> {
  const { data } = await apiClient.get<CallScores>(`/calls/${callId}/scores`);
  return data;
}

export async function fetchSummary(callId: string): Promise<Summary> {
  const { data } = await apiClient.get<Summary>(`/calls/${callId}/summary`);
  return data;
}

export async function fetchCoaching(callId: string): Promise<CoachingData> {
  const { data } = await apiClient.get<CoachingData>(`/calls/${callId}/coaching`);
  return data;
}

export async function resolveObjection(callId: string, objectionId: string): Promise<{ id: string; resolved: boolean }> {
  const { data } = await apiClient.post(`/calls/${callId}/objections/${objectionId}/resolve`);
  return data;
}
