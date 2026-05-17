from __future__ import annotations

import asyncio

import httpx

GATEWAY_URL = "http://localhost:8280"


async def main() -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{GATEWAY_URL}/workflow/task",
            json={
                "project_id": "PRJ-DEMO",
                "title": "Prepare sprint backlog",
                "description": "Import epics and create initial sprint tasks",
                "priority": "high",
                "task_tags": ["backend", "planning"],
                "story_points": 5,
                "actor_id": "PM-001",
                "actor_role": "project_manager",
                "auto_assign": True,
                "notify": True,
            },
        )
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    asyncio.run(main())
