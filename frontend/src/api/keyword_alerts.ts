import apiClient from "./client";
import type { KeywordAlert } from "@/types";

export interface KeywordAlertListResponse {
  data: KeywordAlert[];
  total: number;
}

export async function fetchKeywordAlerts(): Promise<KeywordAlertListResponse> {
  const { data } = await apiClient.get<KeywordAlertListResponse>("/keyword-alerts");
  return data;
}

export async function createKeywordAlert(keyword: string, category = "CUSTOM"): Promise<KeywordAlert> {
  const { data } = await apiClient.post<KeywordAlert>("/keyword-alerts", { keyword, category });
  return data;
}

export async function updateKeywordAlert(
  alertId: string,
  patch: { is_active?: boolean; category?: string }
): Promise<KeywordAlert> {
  const { data } = await apiClient.patch<KeywordAlert>(`/keyword-alerts/${alertId}`, patch);
  return data;
}

export async function deleteKeywordAlert(alertId: string): Promise<void> {
  await apiClient.delete(`/keyword-alerts/${alertId}`);
}
