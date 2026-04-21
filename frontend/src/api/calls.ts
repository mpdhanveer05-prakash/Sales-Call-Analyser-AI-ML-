import apiClient from "./client";
import type { Call, PaginatedResponse, Transcript, CallScores, Summary, CoachingData, CallAnalytics, KeywordHit } from "@/types";

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

export async function cancelCall(callId: string): Promise<Call> {
  const { data } = await apiClient.post<Call>(`/calls/${callId}/cancel`);
  return data;
}

export async function deleteCall(callId: string): Promise<void> {
  await apiClient.delete(`/calls/${callId}`);
}

export async function bulkDeleteCalls(callIds: string[]): Promise<{ deleted: number }> {
  const { data } = await apiClient.post<{ deleted: number }>("/calls/bulk-delete", { call_ids: callIds });
  return data;
}

export async function fetchCallAnalytics(callId: string): Promise<CallAnalytics> {
  const { data } = await apiClient.get<CallAnalytics>(`/calls/${callId}/analytics`);
  return data;
}

export async function fetchKeywordHits(callId: string): Promise<KeywordHit[]> {
  const { data } = await apiClient.get<KeywordHit[]>(`/keyword-alerts/hits/${callId}`);
  return data;
}
