export type TrackerStatus =
  | "found"
  | "prepared"
  | "reviewed"
  | "submitted"
  | "rejected"
  | "interview"
  | "assessment"
  | "offer"
  | "ghosted"
  | "archived";

export interface TrackerEntry {
  job_id: string;
  date_added: string;
  posted_at?: string | null;
  company: string;
  role: string;
  location?: string | null;
  url?: string | null;
  status: TrackerStatus;
  fit_score?: number | null;
  resume_path?: string | null;
  cover_letter_path?: string | null;
  audit_verdict?: string | null;
  latest_resume_version?: number | null;
  notes?: string | null;
  next_action?: string | null;
  starred?: boolean;
  source?: string | null;
  response_date?: string | null;
  response_type?: string | null;
  interview_stage?: string | null;
  source_quality?: number | null;
  date_updated: string;
}

export interface JobAnalysis {
  job_id: string;
  company: string;
  title: string;
  location?: string | null;
  url?: string | null;
  source?: string | null;
  experience_level?: string | null;
  requirements: string[];
  nice_to_haves: string[];
  responsibilities: string[];
  extracted_keywords: string[];
  fit_score: FitScore;
  contact_emails?: string[];
  apply_urls?: string[];
  salary_mentions?: string[];
  raw_excerpt?: string | null;
}

export interface TailorResult {
  job_id: string;
  version: number;
  audit_verdict: string;
  message: string;
}

export interface SearchResult {
  job_id: string;
  company: string;
  role: string;
  status: TrackerStatus;
  fit_score?: number | null;
  snippet: string;
}

export interface SearchResponse {
  query: string;
  matches: SearchResult[];
}

export interface DashboardStats {
  total: number;
  status_counts: Record<string, number>;
  response_rate: number;
  interview_rate: number;
  offer_rate: number;
  response_count: number;
  average_source_quality?: number | null;
}

export interface ScrapeResponse {
  raw_text: string;
  suggested_company?: string | null;
  suggested_title?: string | null;
  final_url?: string | null;
}

export interface SkillMatch {
  skill: string;
  matched: boolean;
  source: string;
}

export interface ProjectScore {
  project_id: string;
  project_name: string;
  relevance_score: number;
  matched_keywords: string[];
  matched_themes: string[];
}

export interface FitScore {
  overall_score: number;
  skill_matches: SkillMatch[];
  skill_match_rate: number;
  nice_to_have_match_rate: number;
  project_scores: ProjectScore[];
  missing_required: string[];
  missing_nice_to_haves: string[];
  recommendation: string;
}

export interface AuditReport {
  total_claims: number;
  passed: number;
  warned: number;
  failed: number;
  hard_constraint_violations: string[];
  overall_verdict: string;
  entries: Array<{
    fact_id: string;
    project_id: string;
    resume_text: string;
    source_text: string;
    verdict: string;
    reason: string;
  }>;
}

export interface PreviewResponse {
  job_id: string;
  company: string;
  title: string;
  location?: string | null;
  requirements: string[];
  extracted_keywords: string[];
  fit_score: FitScore;
  tailored_resume_md: string;
  tailored_resume_html: string;
  audit_report: AuditReport;
  recommendation: string;
}

export interface ConfirmResponse {
  job_id: string;
  version: number;
  resume_path: string;
  audit_verdict: string;
  message: string;
}

export interface OpenClawStatus {
  available: boolean;
  reason: string;
}

export interface CoverLetterResponse {
  job_id: string;
  version: number;
  company: string;
  title: string;
  intro: string;
  body_paragraphs: string[];
  closing: string;
  audit_verdict: string;
  audit_report: AuditReport;
}

export interface CoverLetterList {
  job_id: string;
  versions: number[];
}

export interface BrowserApplyResult {
  job_id: string;
  url: string;
  fields_filled: string[];
  resume_attached: boolean;
  paused: boolean;
  error?: string | null;
}
