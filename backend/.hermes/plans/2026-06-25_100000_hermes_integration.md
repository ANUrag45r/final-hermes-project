# Hermes Vertical AI Agent Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate the core Hermes agent modules into the existing logistics AI agent framework to support meeting-based task management, authentication, and testing, with a hard deadline for project completion on 2026-06-30.

**Architecture:**
The architecture leverages the current modular services (`app/services/hermes`, `app/services/gbrain`) to manage agent control and memory. We will extend `HermesService` to handle the meeting output and enforce the project deadline. Database schema changes will be required to track task completion status relative to the deadline.

**Tech Stack:**
- Python (FastAPI)
- SQLite (`governance_brain.db`)
- Hermes Agent Framework (Control, GStack, PromptBuilder)

---

### Task 1: Extend Hermes Service for Task Tracking
**Objective:** Update `HermesService` to include logic for tracking task progress against the deadline.

**Files:**
- Modify: `app/services/hermes/hermes_service.py`

**Steps:**
1. Update `HermesService` to accept a deadline.
2. Add a method `check_project_status()` that reports progress vs. the 2026-06-30 deadline.
3. Commit.

### Task 2: Database Schema Update
**Objective:** Ensure tracking of task deadlines and status in the DB.

**Files:**
- Modify: `app/models/action_item.py` (Add fields if missing)

**Steps:**
1. Check `app/models/action_item.py` for deadline and completion status fields.
2. If missing, add `due_date: datetime` and `is_completed: bool`.
3. Commit.

### Task 3: API Endpoint for Status
**Objective:** Expose the project status to the user.

**Files:**
- Modify: `app/api/dashboard_routes.py`

**Steps:**
1. Add `GET /dashboard/status` endpoint.
2. Link to `HermesService.check_project_status()`.
3. Commit.

### Task 4: Testing & Deadline Enforcement
**Objective:** Implement a script to verify the project readiness before the 30/06/2026 deadline.

**Files:**
- Modify: `test_governance_brain.db` (update for mock testing)
- Create: `tests/test_deadline_enforcement.py`

**Steps:**
1. Implement test for task completion.
2. Verify system reports "On Track" or "Delayed" based on current date vs deadline.
3. Commit.

---

**Risks & Tradeoffs:**
- Time constraint: Strict 5-day window to 30/06/2026. Prioritize existing infrastructure.
- Scope: Focus only on meeting-derived tasks as requested.

**Open Questions:**
- Are there specific notification requirements for the deadline?
