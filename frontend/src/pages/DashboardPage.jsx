import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";

import { KpiCard } from "../components/KpiCard";
import { TaskBoard } from "../components/TaskBoard";
import { fetchDashboard, setProjectId, toggleTheme } from "../store/appSlice";

export function DashboardPage() {
  const dispatch = useDispatch();
  const { projectId, theme, status, board, forecast, risk, error } = useSelector((state) => state.app);

  useEffect(() => {
    dispatch(fetchDashboard(projectId));
  }, [dispatch, projectId]);

  const mape = Number(forecast?.mape_target_pct || 10);
  const predictedDays = Number(forecast?.predicted_days_to_complete || 0);
  const riskIndex = Number(risk?.risk_index || 0);
  const elapsed = Number(board?.elapsed_ms || 0);

  return (
    <div className={`app theme-${theme}`}>
      <header className="hero">
        <div>
          <p className="eyebrow">TaskFlow Intelligent Assistant</p>
          <h1>Project workspace</h1>
          <p className="sub">Manage tasks, predict deadlines, and balance team load in one flow.</p>
        </div>
        <div className="header-controls">
          <input aria-label="Project ID" value={projectId} onChange={(e) => dispatch(setProjectId(e.target.value))} placeholder="Project ID" />
          <button disabled={status === "loading"} onClick={() => dispatch(fetchDashboard(projectId))}>Refresh</button>
          <button className="ghost" onClick={() => dispatch(toggleTheme())}>Theme</button>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard title="Board Load" value={`${elapsed} ms`} target="< 2000 ms" ok={elapsed <= 2000} />
        <KpiCard title="Forecast MAPE" value={`${mape}%`} target="< 10%" ok={mape <= 10} />
        <KpiCard title="Completion ETA" value={`${predictedDays} days`} target="Predictive" ok={predictedDays > 0} />
        <KpiCard title="Risk Index" value={riskIndex.toFixed(2)} target="As low as possible" ok={riskIndex < 0.35} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Kanban Snapshot</h2>
          <p role="status" aria-live="polite">Status: {status}</p>
        </div>
        {error ? <p className="error">{error}</p> : <TaskBoard columns={board?.data || {}} />}
      </section>
    </div>
  );
}
