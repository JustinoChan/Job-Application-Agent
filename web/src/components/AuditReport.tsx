import type { AuditReport as AuditReportType } from "../api/types";

export default function AuditReport({ report }: { report: AuditReportType }) {
  return (
    <div className="audit-panel">
      <div className={`audit-summary audit-${report.overall_verdict}`}>
        <strong>{report.overall_verdict.toUpperCase()}</strong>
        <span>{report.passed} pass, {report.warned} warn, {report.failed} fail</span>
      </div>
      {report.hard_constraint_violations.length > 0 && (
        <div className="violations">
          {report.hard_constraint_violations.map((violation) => <p key={violation}>{violation}</p>)}
        </div>
      )}
      <table className="application-table compact">
        <thead>
          <tr>
            <th>Verdict</th>
            <th>Source</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {report.entries.map((entry) => (
            <tr key={`${entry.project_id}-${entry.fact_id}`}>
              <td>{entry.verdict}</td>
              <td>{entry.fact_id}</td>
              <td>{entry.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
