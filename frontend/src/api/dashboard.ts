import apiClient from "./client";
import type { TeamDashboard, LeaderboardEntry } from "@/types";

export async function fetchTeamDashboard(period = 30): Promise<TeamDashboard> {
  const { data } = await apiClient.get<TeamDashboard>("/dashboard/team", { params: { period } });
  return data;
}

export async function fetchLeaderboard(period = 30, limit = 10): Promise<LeaderboardEntry[]> {
  const { data } = await apiClient.get<LeaderboardEntry[]>("/dashboard/leaderboard", { params: { period, limit } });
  return data;
}
