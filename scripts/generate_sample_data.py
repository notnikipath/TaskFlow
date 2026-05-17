from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "tasks.json"

STATUSES = ["todo", "in_progress", "review", "done", "blocked"]
PRIORITIES = ["low", "medium", "high", "critical"]
TAGS = ["backend", "frontend", "qa", "infra", "ml", "design", "docs"]


def main() -> None:
    random.seed(42)
    projects = [f"PRJ-{idx:03d}" for idx in range(1, 51)]
    users = [f"USR-{idx:04d}" for idx in range(1, 401)]

    today = date.today()
    records: list[dict] = []
    for idx in range(1, 12001):
        project_id = random.choice(projects)
        status = random.choice(STATUSES)
        priority = random.choice(PRIORITIES)
        due = today + timedelta(days=random.randint(-15, 40))
        tags = random.sample(TAGS, k=random.randint(1, 3))
        records.append(
            {
                "task_id": f"TASK-{idx:05d}",
                "project_id": project_id,
                "title": f"Generated task #{idx}",
                "assignee_id": random.choice(users),
                "priority": priority,
                "status": status,
                "story_points": random.choice([1, 2, 3, 5, 8]),
                "due_date": due.isoformat(),
                "tags": tags,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False)

    print(f"Generated {len(records)} records -> {OUTPUT}")


if __name__ == "__main__":
    main()
