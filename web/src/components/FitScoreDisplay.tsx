import type { FitScore } from "../api/types";

export default function FitScoreDisplay({ fit }: { fit: FitScore }) {
  const matched = fit.skill_matches.filter((match) => match.matched);
  return (
    <div className="fit-panel">
      <div className="fit-score">
        <strong>{Math.round(fit.overall_score * 100)}%</strong>
        <span>{fit.recommendation}</span>
      </div>
      <div className="fit-columns">
        <div>
          <h3>Matches</h3>
          <ul>{matched.map((match) => <li key={match.skill}>{match.skill}</li>)}</ul>
        </div>
        <div>
          <h3>Missing</h3>
          <ul>{fit.missing_required.map((skill) => <li key={skill}>{skill}</li>)}</ul>
        </div>
      </div>
    </div>
  );
}
