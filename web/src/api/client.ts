import axios from "axios";
import type {
  ConfirmResponse,
  DashboardStats,
  OpenClawStatus,
  PreviewResponse,
  ScrapeResponse,
  TrackerEntry,
  TrackerStatus
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "";
const DEV_TOKEN = import.meta.env.VITE_API_TOKEN || localStorage.getItem("JOB_AGENT_API_TOKEN") || "";

export const api = axios.create({
  baseURL: `${API_BASE}/api`,
  withCredentials: true
});

api.interceptors.request.use((config) => {
  if (DEV_TOKEN) {
    config.headers.Authorization = `Bearer ${DEV_TOKEN}`;
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

export async function getRawJob(jobId: string): Promise<string> {
  const response = await api.get<string>(`/applications/${jobId}/raw`, { responseType: "text" });
  return response.data;
}

export function resumeHtmlUrl(jobId: string, version: number): string {
  return `${API_BASE}/api/applications/${jobId}/resume/${version}/html`;
}

export function resumePdfUrl(jobId: string, version: number): string {
  return `${API_BASE}/api/applications/${jobId}/resume/${version}/pdf`;
}

export async function getAudit(jobId: string, version: number) {
  const response = await api.get(`/applications/${jobId}/audit/${version}`);
  return response.data;
}
