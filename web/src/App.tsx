import { Link, NavLink, Route, Routes } from "react-router-dom";
import { useState } from "react";
import AddApplication from "./pages/AddApplication";
import Dashboard from "./pages/Dashboard";
import JobDetail from "./pages/JobDetail";
import Login from "./pages/Login";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => localStorage.getItem("JOB_AGENT_AUTHENTICATED") === "true"
  );

  function handleLogout() {
    localStorage.removeItem("JOB_AGENT_AUTHENTICATED");
    setIsAuthenticated(false);
  }

  if (!isAuthenticated) {
    return <Login onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Job Application Agent</Link>
        <nav>
          <NavLink to="/">Tracker</NavLink>
          <NavLink to="/add">Add</NavLink>
          <button className="nav-button" onClick={handleLogout}>Log Out</button>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/add" element={<AddApplication />} />
        <Route path="/job/:jobId" element={<JobDetail />} />
      </Routes>
    </>
  );
}
