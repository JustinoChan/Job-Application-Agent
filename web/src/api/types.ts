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
  company: string;
  role: string;
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
  date_updated: string;
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

export interface FitScore {
  overall_score: number;
  skill_matches: SkillMatch[];
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
