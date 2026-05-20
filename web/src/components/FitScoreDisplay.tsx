import type { FitScore } from "../api/types";

const REC_LABELS: Record<string, string> = {
  strong: "Strong Match",
  moderate: "Moderate Match",
  weak: "Weak Match",
  skip: "Below Threshold",
};

const REC_CLASSES: Record<string, string> = {
  strong: "rec-strong",
  moderate: "rec-moderate",
  weak: "rec-weak",
  skip: "rec-skip",
};

export default function FitScoreDisplay({ fit }: { fit: FitScore }) {
  const matched = fit.skill_matches.filter((m) => m.matched);
  const recLabel = REC_LABELS[fit.recommendation] || fit.recommendation;
  const recClass = REC_CLASSES[fit.recommendation] || "";

  return (
    <div className="fit-panel">
      <div className="fit-score">
        <strong>{Math.round(fit.overall_score * 100)}%</strong>
        <span className={`rec-badge ${recClass}`}>{recLabel}</span>
      </div>

      <div className="fit-rates">
        <div className="rate-item">
          <span className="rate-label">Required skills</span>
          <span className="rate-value">{Math.round((fit.skill_match_rate ?? 0) * 100)}%</span>
        </div>
        <div className="rate-item">
          <span className="rate-label">Nice-to-haves</span>
          <span className="rate-value">{Math.round((fit.nice_to_have_match_rate ?? 0) * 100)}%</span>
        </div>
      </div>

      <div className="fit-columns">
        <div>
          <h3>Matched Skills ({matched.length})</h3>
          <ul>
            {matched.map((m) => (
              <li key={m.skill}>
                {m.skill}
                {m.source && <span className="skill-source">{m.source}</span>}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3>Missing ({fit.missing_required.length})</h3>
          <ul>{fit.missing_required.map((skill) => <li key={skill}>{skill}</li>)}</ul>
        </div>
      </div>

      {fit.project_scores && fit.project_scores.length > 0 && (
        <div className="project-scores">
          <h3>Project Relevance</h3>
          {fit.project_scores.map((ps) => (
            <div key={ps.project_id} className="project-score-row">
              <div className="project-score-header">
                <span className="project-score-name">{ps.project_name}</span>
                <span className="project-score-pct">{Math.round(ps.relevance_score * 100)}%</span>
              </div>
              <div className="project-score-bar-bg">
                <div
                  className="project-score-bar-fill"
                  style={{ width: `${Math.round(ps.relevance_score * 100)}%` }}
                />
              </div>
              {ps.matched_keywords.length > 0 && (
                <div className="project-score-keywords">
                  {ps.matched_keywords.map((kw) => (
                    <span key={kw} className="chip">{kw}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
