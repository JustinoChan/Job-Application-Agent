import axios from "axios";
import type {
  ConfirmResponse,
  CoverLetterList,
  CoverLetterResponse,
  DashboardStats,
  JobAnalysis,
  OpenClawStatus,
  PreviewResponse,
  ScrapeResponse,
  SearchResponse,
  TailorResult,
  TrackerEntry,
  TrackerStatus
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "";

function getStoredToken(): string {
  return localStorage.getItem("JOB_AGENT_API_TOKEN") || import.meta.env.VITE_API_TOKEN || "";
}

function withToken(url: string): string {
  const token = getStoredToken();
  if (!token) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function listApplications(includeArchived = false): Promise<TrackerEntry[]> {
  const response = await api.get<TrackerEntry[]>("/applications/", {
    params: { include_archived: includeArchived }
  });
  return response.data;
}

export async function getApplication(jobId: string): Promise<TrackerEntry> {
  const response = await api.get<TrackerEntry>(`/applications/${jobId}`);
  return response.data;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await api.get<DashboardStats>("/dashboard/stats");
  return response.data;
}

export async function getOpenClawStatus(): Promise<OpenClawStatus> {
  const response = await api.get<OpenClawStatus>("/applications/openclaw-status");
  return response.data;
}

export async function scrapeJob(url: string, provider?: string): Promise<ScrapeResponse> {
  const response = await api.post<ScrapeResponse>("/applications/scrape", { url, provider });
  return response.data;
}

export async function previewApplication(payload: {
  raw_text: string;
  company?: string;
  title?: string;
  url?: string;
}): Promise<PreviewResponse> {
  const response = await api.post<PreviewResponse>("/applications/preview", payload);
  return response.data;
}

export async function confirmApplication(payload: {
  raw_text: string;
  company?: string;
  title?: string;
  url?: string;
}): Promise<ConfirmResponse> {
  const response = await api.post<ConfirmResponse>("/applications/confirm", payload);
  return response.data;
}

export async function updateStatus(
  jobId: string,
  status: TrackerStatus,
  notes?: string
): Promise<TrackerEntry> {
  const response = await api.put<TrackerEntry>(`/applications/${jobId}/status`, { status, notes });
  return response.data;
}

export async function toggleStar(jobId: string, starred: boolean): Promise<TrackerEntry> {
  const response = await api.put<TrackerEntry>(`/applications/${jobId}/star`, { starred });
  return response.data;
}

export async function bulkArchive(jobIds: string[]): Promise<{ updated: number }> {
  const response = await api.post<{ updated: number }>("/applications/bulk-archive", { job_ids: jobIds });
  return response.data;
}

export async function searchPostings(query: string): Promise<SearchResponse> {
  const response = await api.get<SearchResponse>("/applications/search", {
    params: { q: query }
  });
  return response.data;
}

export async function getRawJob(jobId: string): Promise<string> {
  const response = await api.get<string>(`/applications/${jobId}/raw`, { responseType: "text" });
  return response.data;
}

export function resumeHtmlUrl(jobId: string, version: number): string {
  return withToken(`${API_BASE}/api/applications/${jobId}/resume/${version}/html`);
}

export function resumePdfUrl(jobId: string, version: number): string {
  return withToken(`${API_BASE}/api/applications/${jobId}/resume/${version}/pdf`);
}

export async function getJobAnalysis(jobId: string): Promise<JobAnalysis> {
  const response = await api.get<JobAnalysis>(`/applications/${jobId}/analysis`);
  return response.data;
}

export async function tailorFromTracker(jobId: string): Promise<TailorResult> {
  const response = await api.post<TailorResult>(`/applications/${jobId}/tailor`);
  return response.data;
}

export async function getAudit(jobId: string, version: number) {
  const response = await api.get(`/applications/${jobId}/audit/${version}`);
  return response.data;
}

export async function generateCoverLetter(
  jobId: string,
  resumeVersion?: number
): Promise<CoverLetterResponse> {
  const response = await api.post<CoverLetterResponse>(
    `/applications/${jobId}/cover-letter`,
    { resume_version: resumeVersion ?? null }
  );
  return response.data;
}

export async function listCoverLetters(jobId: string): Promise<CoverLetterList> {
  const response = await api.get<CoverLetterList>(`/applications/${jobId}/cover-letters`);
  return response.data;
}

export async function getCoverLetterAudit(jobId: string, version: number) {
  const response = await api.get(`/applications/${jobId}/cover-letter/${version}/audit`);
  return response.data;
}

export function coverLetterHtmlUrl(jobId: string, version: number): string {
  return withToken(`${API_BASE}/api/applications/${jobId}/cover-letter/${version}/html`);
}

export function coverLetterPdfUrl(jobId: string, version: number): string {
  return withToken(`${API_BASE}/api/applications/${jobId}/cover-letter/${version}/pdf`);
}
