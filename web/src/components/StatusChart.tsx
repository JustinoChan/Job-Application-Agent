import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

const colors: Record<string, string> = {
  found: "#94a3b8",
  prepared: "#4f46e5",
  reviewed: "#2563eb",
  submitted: "#059669",
  interview: "#0d9488",
  assessment: "#7c3aed",
  offer: "#059669",
  rejected: "#dc2626",
  ghosted: "#cbd5e1"
};

export default function StatusChart({ counts }: { counts: Record<string, number> }) {
  const data = Object.entries(counts)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({ name, value }));

  if (data.length === 0) {
    return (
      <div className="donut-empty">
        <span>No data</span>
      </div>
    );
  }

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={160}>
        <PieChart>
          <Pie data={data} innerRadius={46} outerRadius={70} dataKey="value">
            {data.map((entry) => (
              <Cell key={entry.name} fill={colors[entry.name] || "#44403c"} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
