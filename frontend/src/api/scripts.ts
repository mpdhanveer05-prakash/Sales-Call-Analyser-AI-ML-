import apiClient from "./client";
import type { Script, ScriptRubric } from "@/types";

export async function fetchScripts(activeOnly = true): Promise<Script[]> {
  const { data } = await apiClient.get<Script[]>("/scripts", { params: { active_only: activeOnly } });
  return data;
}

export async function fetchScript(id: string): Promise<Script> {
  const { data } = await apiClient.get<Script>(`/scripts/${id}`);
  return data;
}

export async function createScript(payload: { name: string; content: string; rubric?: ScriptRubric; is_active?: boolean }): Promise<Script> {
  const { data } = await apiClient.post<Script>("/scripts", payload);
  return data;
}

export async function updateScript(
  id: string,
  payload: { name?: string; content?: string; rubric?: ScriptRubric; is_active?: boolean },
): Promise<Script> {
  const { data } = await apiClient.patch<Script>(`/scripts/${id}`, payload);
  return data;
}
