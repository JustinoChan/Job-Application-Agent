import { FormEvent, useState } from "react";

interface LoginProps {
  onLogin: () => void;
}

const USERNAME = "justin";
const PASSWORD = "chan";

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (username.trim().toLowerCase() === USERNAME && password === PASSWORD) {
      localStorage.setItem("JOB_AGENT_AUTHENTICATED", "true");
      onLogin();
      return;
    }
    setError("Invalid username or password.");
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
          <label>Username</label>
          <input
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>
        <div>
          <label>Password</label>
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <button type="submit">Log In</button>
      </form>
    </main>
  );
}
