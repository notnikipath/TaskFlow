import React from "react";

export function TaskBoard({ columns }) {
  const keys = Object.keys(columns || {});
  if (!keys.length) {
    return <div className="empty-board">No tasks yet. Run workflow to populate board.</div>;
  }

  return (
    <section className="board-grid">
      {keys.map((columnKey) => (
        <div className="board-column" key={columnKey}>
          <h3>{columnKey.replaceAll("_", " ")}</h3>
          {(columns[columnKey] || []).map((task) => (
            <article className="task-card" key={task.task_id}>
              <p className="task-id">{task.task_id}</p>
              <p className="task-title">{task.title}</p>
              <p className="task-meta">{task.priority} • {task.assignee_id || "unassigned"}</p>
            </article>
          ))}
        </div>
      ))}
    </section>
  );
}