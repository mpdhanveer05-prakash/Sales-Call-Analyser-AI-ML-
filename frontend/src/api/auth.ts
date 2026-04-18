import apiClient from "./client";
import type { User } from "@/types";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", { email, password });
  return data;
}

export async function refreshToken(refreshToken: string): Promise<{ access_token: string }> {
  const { data } = await apiClient.post<{ access_token: string }>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}
