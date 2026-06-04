import type { DashboardStats } from "../api/types";

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function QuickStats({ stats }: { stats: DashboardStats | null }) {
  return (
    <div className="stat-list">
      <div><span>Response rate</span><strong>{stats ? percent(stats.response_rate) : "-"}</strong></div>
      <div><span>Responses</span><strong>{stats ? stats.response_count : "-"}</strong></div>
      <div><span>Interview rate</span><strong>{stats ? percent(stats.interview_rate) : "-"}</strong></div>
      <div><span>Offer rate</span><strong>{stats ? percent(stats.offer_rate) : "-"}</strong></div>
      <div><span>Avg source quality</span><strong>{stats?.average_source_quality ?? "-"}</strong></div>
    </div>
  );
}
