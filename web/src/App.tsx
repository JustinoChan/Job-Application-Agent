import { Link, NavLink, Route, Routes } from "react-router-dom";
import AddApplication from "./pages/AddApplication";
import Dashboard from "./pages/Dashboard";
import JobDetail from "./pages/JobDetail";

export default function App() {
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">Job Application Agent</Link>
        <nav>
          <NavLink to="/">Tracker</NavLink>
          <NavLink to="/add">Add</NavLink>
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
