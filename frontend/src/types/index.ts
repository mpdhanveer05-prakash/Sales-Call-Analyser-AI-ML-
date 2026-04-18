export type UserRole = "ADMIN" | "MANAGER" | "AGENT";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export type CallStatus =
  | "QUEUED"
  | "TRANSCRIBING"
  | "ANALYZING"
  | "SCORING"
  | "COMPLETED"
  | "FAILED";

export interface Call {
  id: string;
  agent_id: string;
  agent_name: string;
  call_date: string;
  duration_seconds: number | null;
  status: CallStatus;
  disposition: string | null;
  speech_score: number | null;
  sales_score: number | null;
  original_filename: string;
  uploaded_at: string;
}

export interface Agent {
  id: string;
  user_id: string;
  employee_id: string | null;
  full_name: string;
  email: string;
  team_id: string | null;
  team_name: string | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pages: number;
}

export interface ApiError {
  error: string;
  code: string;
}
