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

export interface TranscriptSegment {
  id: string;
  speaker: "AGENT" | "CUSTOMER";
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number | null;
}

export interface Transcript {
  id: string;
  call_id: string;
  language: string | null;
  duration_seconds: number | null;
  segment_count: number;
  segments: TranscriptSegment[];
  created_at: string;
}

export interface SpeechScore {
  id: string;
  call_id: string;
  pronunciation: number;
  intonation: number;
  fluency: number;
  grammar: number;
  vocabulary: number;
  pace: number;
  clarity: number;
  filler_score: number;
  composite: number;
  fillers_per_min: number | null;
  pace_wpm: number | null;
  talk_ratio: number | null;
  created_at: string;
}

export interface CallScores {
  call_id: string;
  speech: SpeechScore | null;
  sales: null;
}
