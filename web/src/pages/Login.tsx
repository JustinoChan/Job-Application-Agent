import { FormEvent, useState } from "react";
import axios from "axios";

interface LoginProps {
  onLogin: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || "";

export default function Login({ onLogin }: LoginProps) {
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [verifying, setVerifying] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const trimmed = token.trim();
    if (!trimmed) {
      setError("Enter your API token.");
      return;
    }

    setVerifying(true);
    try {
      await axios.get(`${API_BASE}/api/applications/openclaw-status`, {
        headers: { Authorization: `Bearer ${trimmed}` }
      });
      localStorage.setItem("JOB_AGENT_API_TOKEN", trimmed);
      localStorage.setItem("JOB_AGENT_AUTHENTICATED", "true");
      onLogin();
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 401) {
        setError("Token rejected by the server.");
      } else if (status === undefined) {
        setError("Could not reach the API. Check the tunnel.");
      } else {
        setError(err.response?.data?.detail || err.message);
      }
    } finally {
      setVerifying(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={handleSubmit}>
        <div>
          <p className="login-kicker">Private Dashboard</p>
          <h1>Job Application Agent</h1>
        </div>
        {error && <div className="error-banner">{error}</div>}
        <div>
          <label>API Token</label>
          <input
            autoComplete="current-password"
            autoFocus
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Paste the API_TOKEN from .env"
          />
        </div>
        <button type="submit" disabled={verifying}>
          {verifying ? "Verifying..." : "Log In"}
        </button>
      </form>
    </main>
  );
}
