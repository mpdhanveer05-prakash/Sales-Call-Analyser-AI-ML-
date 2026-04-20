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
  | "FAILED"
  | "CANCELLED";

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

export interface SalesScore {
  id: string;
  call_id: string;
  greeting: number;
  rapport: number;
  discovery: number;
  value_explanation: number;
  objection_handling: number;
  script_adherence: number;
  closing: number;
  compliance: number;
  composite: number;
  details: Record<string, { score: number; justification: string; quote: string }> | null;
  created_at: string;
}

export interface CallScores {
  call_id: string;
  speech: SpeechScore | null;
  sales: SalesScore | null;
}

export interface Summary {
  id: string;
  call_id: string;
  executive_summary: string;
  key_moments: string[];
  coaching_suggestions: string[];
  disposition_confidence: number | null;
  disposition_reasoning: string | null;
  created_at: string;
}

export interface ScriptRubric {
  required_points: string[];
  prohibited_phrases: string[];
  required_disclosures: string[];
}

export interface Script {
  id: string;
  name: string;
  content: string;
  rubric: ScriptRubric;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SearchResult {
  call_id: string;
  agent_id: string | null;
  agent_name: string | null;
  call_date: string | null;
  disposition: string | null;
  speech_score: number | null;
  sales_score: number | null;
  duration_seconds: number | null;
  highlights: string[];
  matched_segment: { start_ms: number; text: string } | null;
  score: number;
}

export interface ScoreTrendPoint {
  week: string;
  avg_speech: number | null;
  avg_sales: number | null;
  call_count: number;
}

export interface AgentScorecard {
  agent_id: string;
  agent_name: string;
  employee_id: string | null;
  team_name: string | null;
  call_count: number;
  avg_speech_score: number | null;
  avg_sales_score: number | null;
  disposition_breakdown: Record<string, number>;
  score_trend: ScoreTrendPoint[];
  strengths: string[];
  weaknesses: string[];
}

export interface LeaderboardEntry {
  rank: number;
  agent_id: string;
  agent_name: string;
  call_count: number;
  avg_speech_score: number | null;
  avg_sales_score: number | null;
  composite_score: number | null;
}

export interface TeamDashboard {
  total_calls: number;
  avg_speech_score: number | null;
  avg_sales_score: number | null;
  conversion_rate: number | null;
  disposition_breakdown: Record<string, number>;
  weekly_trend: ScoreTrendPoint[];
  leaderboard: LeaderboardEntry[];
}

export interface CoachingClip {
  id: string;
  call_id: string;
  start_ms: number;
  end_ms: number;
  category: string;
  reason: string;
  created_at: string;
}

export interface Objection {
  id: string;
  call_id: string;
  timestamp_ms: number;
  objection_type: string;
  quote: string;
  resolved: boolean;
  created_at: string;
}

export interface CoachingData {
  coaching_clips: CoachingClip[];
  objections: Objection[];
}
