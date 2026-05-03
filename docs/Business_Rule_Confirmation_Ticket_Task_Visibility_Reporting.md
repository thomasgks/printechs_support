# Business Rule Confirmation — Ticket → Task → Customer Visibility → Reporting

**Document type:** Business analysis / solution design (pre-mobile, pre-code)  
**Version:** 1.0  
**Alignment:** ERPNext / Frappe — `Support Ticket`, `Support Task`, ticket comments, reporting  
**Purpose:** Confirm and refine end-to-end process before mobile application development  

---

## 1. Executive Summary

This document **confirms** a practical business model for **implementation-style support work** where:

- A **Support Ticket** is the **parent case** (the customer-visible “container” for the request).
- **Support Tasks** are **execution lines** under that ticket (design, mockup, API, go-live, etc.).
- **Customer progress** is communicated through a **controlled combination** of ticket-level messages, **customer-relevant tasks or milestones**, and **notifications**—without exposing every internal technical task by default.
- **Overdue and delay** are tracked primarily at **task level** (dates + delay fields) and **summarized** at **ticket level** for management and mobile dashboards.

Your existing ERPNext design already supports the **core parent–child shape**: `Support Task.support_ticket` (required), per-task **assignees**, **responsible side**, **planned/actual dates**, **due date**, **status**, **delay** fields, optional **predecessor** for sequencing, and **project_plan_progress** for percentage. The **refinements** below focus on **how to use** those fields consistently, **customer visibility rules**, **status governance**, and **reporting** so the same model works for **Desk, portal, and mobile**.

**Key decisions stated up front**

| Topic | Confirmed recommendation |
|-------|-------------------------|
| Parent–child | **Yes** — one ticket, many tasks; ticket = case; tasks = execution plan |
| Task fields | **Yes** — assignee(s), responsible side, dates, status, delay, notes, evidence — per task |
| Progress % | **Yes** at task level (`project_plan_progress` or status-derived); ticket roll-up **recommended** as derived metric |
| Dependencies | **Optional** — use **predecessor** when needed; allow **parallel** tasks otherwise |
| Customer approval | **Both** — **task** (“Get approval”) + **ticket status** `Waiting for Approval` when the whole case waits on sign-off |
| Waiting for customer | **Both** — **task status** for specific blockers; **ticket status** when the whole ticket is blocked |
| Customer visibility | **Tiered** — milestones / customer-action tasks visible; **internal** tasks hidden unless flagged |
| Overdue | **Task-first** SLA; ticket **summary** flags from worst child + ticket due date |

---

## 2. Confirmed Business Flow

### 2.1 End-to-end flow (aligned with your narrative)

| Step | Actor | Action | System outcome |
|------|--------|--------|----------------|
| 1 | Customer | Creates **Support Ticket** | Ticket in **Draft** or **Open** (per your intake rules); customer record linked |
| 2 | Manager | Reviews queue | Ticket triaged (priority, type, agreement if applicable) |
| 3 | Manager | Assigns ticket | Assignment to **technician** and/or **team**; status moves toward **Acknowledged** / **In Progress** per policy |
| 4 | Technician | Starts execution | Ticket **In Progress**; first **customer-visible** update optional |
| 5 | Technician | Creates **multiple Support Tasks** under ticket | Tasks carry **dates**, **owners**, **types** (e.g. Development, Implementation Step, Customer Action) |
| 6 | Various | Work, wait, complete tasks | Status transitions; **Waiting for Customer** / **Waiting for Printechs** at **task** level; ticket may mirror |
| 7 | Customer | Responds / approves / uploads | When blocked on customer, **task** and/or **ticket** shows waiting state; **comments** log customer-visible text |
| 8 | Technician / Manager | Resolve and close | Ticket **Resolved** → **Closed**; tasks **Completed** or **Cancelled** |

### 2.2 Flow diagram (conceptual)

```text
[Customer] --creates--> [Support Ticket: case]
                              |
                              v
[Manager] --assigns--> [Ticket: owned / assigned]
                              |
                              v
[Technician] --creates--> [Support Task 1..n: execution plan]
                              |
            +-----------------+------------------+
            |                 |                  |
            v                 v                  v
   [Parallel tasks]   [Sequential chain]   [Customer task]
   (independent)       (predecessor link)    (Customer Action type)
```

---

## 3. Ticket vs Task Design Recommendation

### 3.1 Relationship

| Question | Confirmation |
|----------|--------------|
| Is one Support Ticket the parent case? | **Yes.** The ticket is the **contractual / operational case** for the customer request (e.g. “Vehicle Tracking module”). |
| Are multiple Support Tasks execution steps under the ticket? | **Yes.** Each task is a **line of work** with its own schedule and ownership. |
| Optional ERPNext Project? | **Optional.** Link ticket/tasks to **Project** when you need Gantt roll-up or cross-ticket project reporting; not mandatory for every ticket. |

### 3.2 Per-task attributes (confirm use of existing fields)

| Attribute | Confirm | Notes |
|-----------|---------|--------|
| Assigned person(s) | **Yes** | Use **Task Assignees** + **Assigned To User (Primary)** for reporting. |
| Responsible side | **Yes** | Use **Printechs / Customer / Shared** to drive “who must act next” in customer views. |
| Planned start / end | **Yes** | **planned_start_date**, **planned_end_date** for planning and Gantt. |
| Due date | **Yes** | Primary operational deadline for **overdue** logic. |
| Actual start / end | **Yes** | **actual_start_date**, **actual_end_date** for as-built timeline. |
| Status | **Yes** | Task drives day-to-day execution state. |
| Delay reason / owner / remarks | **Yes** | When **Delayed** or overdue with explanation, **delay_reason** (link), **delay_owner**, **delay_remarks**. |
| Remarks / history | **Yes** | **description**, **completion_notes**; **version history** via DocType track changes; **structured history** via ticket/task comments (see §8). |

### 3.3 Completion percentage

| Topic | Recommendation |
|-------|------------------|
| Per-task % | **Yes.** Use **project_plan_progress** when you need fine-grained % (especially if linked to ERPNext **Project Task**). If not linked, derive **0 / 50 / 100** from status (e.g. In Progress → 50%, Completed → 100%) per your technical spec. |
| Ticket overall progress | **Recommended: derived.** Formula example: **average** of non-cancelled tasks, or **weighted** by task type—define one rule and apply consistently in reports and mobile. **Do not** duplicate manual % on ticket unless you need a contractual override. |

### 3.4 Detailed planning model (implementation / development tickets)

| Topic | Recommendation |
|-------|----------------|
| Sequential vs parallel | **Both allowed.** Default **parallel** for independent streams (e.g. “API” vs “Screen design”); use **predecessor_task** when B cannot start until A finishes. |
| Task dependency | **Required only when** business logic demands it. Otherwise keep tasks independent to reduce admin friction. |
| Customer approval | **Represent as:** (1) a **task** with type **Customer Action** or **UAT** / subject “Get approval from customer”; (2) **ticket status** **Waiting for Approval** when the **entire** ticket is blocked on approval. Use **both** when the approval gate is major (e.g. signed mockup). |
| “Waiting for Customer” | **Track at task level** for **specific** blockers (e.g. “Provide credentials”). **Promote to ticket level** when **no** further internal work can proceed until customer acts. They can coexist. |
| Overdue | **Task:** due_date vs now; **is_delayed** flag + delay fields when explained. **Ticket:** summarize **worst** open task (e.g. max overdue days) + optional **ticket due date** if you use it. |

---

## 4. Status Design Recommendation

### 4.1 Ticket statuses (aligned with your DocType)

Your **Support Ticket** options include: **Draft, Open, Acknowledged, In Progress, Waiting for Customer, Waiting for Internal Team, Waiting for Approval, Resolved, Closed, Cancelled, Reopened**.

| Status | Meaning | Typical entry | Who changes |
|--------|----------|---------------|-------------|
| **Draft** | Not yet submitted / internal | Save before customer send | Creator, coordinator |
| **Open** | Logged, not yet in active work | Submission | System / coordinator |
| **Acknowledged** | Receipt confirmed | Auto or manager | Manager, coordinator |
| **In Progress** | Active work | Assignment or start | Manager, technician |
| **Waiting for Customer** | Case blocked on customer | Customer action required | Technician, manager |
| **Waiting for Internal Team** | Blocked internally (vendor, dev queue) | Dependency | Technician, manager |
| **Waiting for Approval** | Approval gate (scope, budget, mockup) | Before build | Manager, technician |
| **Resolved** | Proposed complete | All work done | Technician, manager |
| **Closed** | Accepted / archived | Confirmation | Manager, customer (if policy) |
| **Cancelled** | Will not do | Business decision | Manager |
| **Reopened** | Issue returned | After closure | Customer, manager |

**Note:** There is **no separate “Assigned”** in your list; **assignment** is a **field** (assignees). If you need a distinct “Assigned” state, add it via change management—otherwise treat **Acknowledged/ In Progress** as assigned.

**Events and remarks**

| Transition | Mandatory remark? | Typical rule |
|------------|-------------------|--------------|
| → **Waiting for Customer** | **Recommended** | Short customer-visible comment on **ticket** |
| → **Cancelled** | **Yes** | Reason code / text |
| → **Resolved** / **Closed** | **Recommended** | Resolution notes / closure category |
| **Delay reason** | **Mandatory when** marking **Delayed** or when **is_delayed** set with customer impact | Per your Delay Reason master |

### 4.2 Task statuses (aligned with your DocType)

Your **Support Task** options include: **Open, In Progress, Waiting for Customer, Waiting for Printechs, Completed, Cancelled, Delayed**.

| Status | Meaning | Who changes |
|--------|----------|-------------|
| **Open** | Planned, not started | Technician, assignee |
| **In Progress** | Active | Assignee |
| **Waiting for Customer** | Customer must act | Assignee |
| **Waiting for Printechs** | Internal dependency | Assignee |
| **Completed** | Done | Assignee, manager |
| **Cancelled** | Superseded | Technician, manager |
| **Delayed** | Off-track with reason | Assignee (with delay fields) |

**Gap vs your candidate list:** “**Waiting for Approval**” is **not** currently in **Support Task** status options. **Recommended mapping:**

- **Option A (minimal):** Use ticket **Waiting for Approval** + task **Waiting for Customer** or **In Progress** with subject “Approval pending” until you extend task status.
- **Option B (cleaner):** Add **Waiting for Approval** to **Support Task** options (configuration change) for approval gates **without** blocking the whole ticket.

**When delay reason is mandatory**

- When status → **Delayed**, or **is_delayed** is checked: require **delay_reason** (and **delay_owner** when not obvious).
- When **overdue** (past **due_date**) and work continues: either auto-set **Delayed** or require acknowledgment with delay fields (pick one policy and automate in ERPNext).

---

## 5. Date and Overdue Tracking Logic

### 5.1 Per-task fields (recommended usage)

| Field | Purpose |
|-------|---------|
| **planned_start_date** | Plan baseline; Gantt start |
| **planned_end_date** | Plan end window |
| **due_date** | **Primary** SLA / operational deadline for overdue |
| **actual_start_date** | First touch / real start |
| **actual_end_date** | **Completion** time (pair with Completed) |
| **reminder_datetime** + **send_email_reminder** | User reminders (not SLA) |
| **delay_days** | **System-calculated** (read-only in your model) — business days vs calendar per spec |
| **delay_owner / delay_reason / delay_remarks** | Accountability + audit |
| **completion_notes / outcome / evidence_attachment** | Closure quality |

### 5.2 Overdue calculation

| Level | Definition |
|-------|------------|
| **Task overdue** | `due_date` < now AND status **not** in (Completed, Cancelled). Optional grace minutes. |
| **Task delayed** | **Business** concept: blocked or late **with reason** — use **Delayed** status and/or **is_delayed** + delay fields. |
| **Ticket overdue** | If ticket has **due_date**: compare to now. Else **derive**: e.g. **any** open task overdue OR **max** overdue days among open tasks. |

### 5.3 Auto vs manual

| Behavior | Recommendation |
|----------|----------------|
| **Overdue flag** | **Compute in reports** (no need for a stored “overdue” on every row if queries are clear). |
| **Delayed status** | **Manual or semi-auto** — e.g. prompt when due_date passed and status still open: “Mark Delayed or extend due date.” |

### 5.4 Reports appearance

- **Delayed tasks:** filter `status == Delayed` OR `is_delayed == 1` OR overdue > N days per policy.
- **Ticket summary:** columns: **open tasks count**, **overdue tasks count**, **max delay days**, **ticket due** vs **today**.

---

## 6. Customer Visibility Model

### 6.1 Design principle

**Customers should see progress without seeing every internal task.** Use **three layers**:

| Layer | Content | Audience |
|-------|---------|----------|
| **A — Ticket narrative** | Customer-visible **ticket comments**; status; subject; high-level timeline | Customer |
| **B — Customer-visible milestones** | Subset of tasks: **Customer Action**, **UAT**, **Go Live**, or tasks flagged “visible” | Customer |
| **C — Internal execution** | Technical tasks (DB design, API internals) | Internal only |

### 6.2 What customer can see (portal / mobile)

| Data | Default |
|------|---------|
| Ticket subject, status, priority (if policy) | **Yes** |
| Full internal task list | **No** (unless you add a “Customer visible” flag per task) |
| **Milestone** tasks (by type or flag) | **Yes** — name, status, due date, responsible side |
| Internal notes | **No** |
| **Pending action** | **Yes** — derived from **Waiting for Customer** at ticket or task |
| Attachments | **Yes** — customer-visible attachments and comments only |
| Remarks | **Yes** — only **customer-visible** comment rows / text |

**Practical rule:** If your technical spec does not yet have **“customer_visible” on Support Task**, use **task_type** (e.g. **Customer Action**, **UAT**, **Implementation Step** for go-live) to drive portal visibility, or add a **Check** field in a future iteration.

### 6.3 Notifications (customer)

| Event | Notify customer? |
|-------|------------------|
| Ticket assigned / ownership change | **Yes** (if policy) |
| Task **Waiting for Customer** | **Yes** |
| Approval required | **Yes** |
| Task overdue (customer-owned) | **Yes** |
| Milestone completed / go-live scheduled | **Yes** (milestone tasks) |
| Internal technical task completed | **Optional** — aggregate as “Progress update” on ticket |

### 6.4 Timeline / history

- **Customer timeline** = **Ticket comments** (customer-visible) + **visible milestone** task status changes (if exposed) + **email** events.
- **Internal timeline** = full **Support Task** history + internal comments.

---

## 7. Reporting Model

Each report: **purpose**, **columns**, **filters**, **grain**, **presentation**.

| # | Report / widget | Purpose | Key columns | Filters | Grain | Format |
|---|-------------------|---------|-------------|---------|-------|--------|
| 1 | **Tasks per ticket** | Count workload | Ticket, total, open, completed | Date, customer | Ticket | Report + dashboard widget |
| 2 | **Completed vs pending tasks** | Throughput | Task, status, assignee, due | Assignee, date | Task | Report |
| 3 | **Delayed tasks** | Risk management | Task, delay_reason, delay_owner, days | Division, customer | Task | Report |
| 4 | **Overdue tasks** | SLA breach | Task, due_date, overdue days | Team | Task | Dashboard + list |
| 5 | **Pending with customer** | Unblock customer | Ticket/task, since when | Customer | Both | Dashboard |
| 6 | **Pending with Printechs** | Internal backlog | Queue by assignee | Team | Task | Dashboard |
| 7 | **Engineer load** | Capacity | Open tasks per user | Date | User | Chart |
| 8 | **Customer pending approvals** | Revenue / gate | Approval tasks, ticket | Customer | Task | Report |
| 9 | **Implementation progress** | PM view | % complete, milestones | Project/ticket | Ticket | Report |
|10 | **Printable project plan** | Stakeholder | Gantt-style list: task, dates, owner | Ticket | Task | Print |

**Widget vs report:** Use **widgets** for **role landing** (my overdue, my waiting); **reports** for export and **print** for static plans.

---

## 8. Communication and Update History Model

### 8.1 What to store where

| Update type | Where | Customer sees? |
|-------------|-------------|----------------|
| Quick status (“started API”) | **Task** description / internal notes | No |
| Customer-facing message | **Support Ticket Comment** (customer-visible) | Yes |
| Formal approval | **Ticket** status + **comment** + optional **task** | Yes |
| Evidence | **Task attachment** / **evidence_attachment** | Only if linked to customer-visible context |
| **Progress remarks** | Task **description** + **version history** | Internal only |
| **Completion** | **completion_notes** + **outcome** | Internal; **summary** in ticket comment for customer |

### 8.2 Child table vs timeline

| Approach | Recommendation |
|----------|----------------|
| **Ticket comments (child table)** | **Primary** customer-visible channel (already fits portal). |
| **Task-level threaded log** | If needed, add **Support Task Comment** child table or use **Frappe Comments** on Support Task with visibility flag — **second phase** if task chatter is heavy. |
| **Audit** | DocType **track_changes** on Support Task + ticket comments for compliance. |

---

## 9. Mobile Readiness Recommendation

### 9.1 Mandatory actions by role

| Role | Must have on mobile |
|------|---------------------|
| **Manager** | Ticket list, **assign/reassign**, **progress summary** (tasks + overdue), **notifications** |
| **Technician** | **My tickets**, **create/edit tasks**, **status**, **due dates**, **delay**, **photos** (attachments), **waiting for customer** |
| **Customer** | **My tickets**, **comments**, **attachments**, **pending actions**, **milestone** (or simplified) task list, **push** |

### 9.2 Mandatory screens (mobile)

1. **Login / home**  
2. **Ticket list** (filters)  
3. **Ticket detail** (header + **comments**)  
4. **Task list** (by ticket) — internal full; customer **filtered**  
5. **Task detail** (edit for internal)  
6. **Notifications**  
7. **Attachments** (camera upload)  

---

## 10. Full Worked Example — Vehicle Tracking Ticket

**Ticket:** “Develop additional module: Vehicle Tracking”  
**Type:** Additional Development / Change Request / Enhancement  

| Phase | Ticket / task | Owner | Dates | Status | Customer-visible? |
|-------|----------------|-------|-------|--------|-------------------|
| Create | Customer creates ticket | — | Day 0 | **Open** | Yes (subject) |
| Triage | Manager assigns to **Ali** | Manager | Day 1 | **In Progress** | Optional “Assigned” message |
| Plan | Ali creates tasks 1–7 | Ali | Day 1 | Tasks **Open** | **No** (internal plan) unless milestones published |
| Work | Task 1 “Design DB” | Dev | Due D+5 | **In Progress** → **Completed** | Optional aggregate |
| Parallel | Task 2 “Design Screen” + 3 “Mockup” | UX | Overlap | **In Progress** | **Yes** for mockup when shared |
| Approval | Task 4 “Get approval from customer” | Customer | Due D+10 | **Waiting for Customer** | **Yes** + ticket **Waiting for Approval** |
| Delay | Task 5 “API Development” | Dev | Due passed | **Delayed** + reason | Internal; ticket comment “API delayed by …” if customer impact |
| Done | Task 5 completed | Dev | D+15 | **Completed** | Milestone note |
| Go-live | Task 7 “Go Live” | Ali | Scheduled | **In Progress** → **Completed** | **Yes** |
| Close | Ticket | Manager | **Resolved** → **Closed** | **Yes** |

**Progress:** Ticket shows **e.g. 5/7 tasks completed** or **weighted %**; customer sees **milestones** + **comments**, not necessarily all seven internal lines.

**Manager overdue view:** Dashboard shows Task 5 **Delayed** and **overdue days**; ticket flagged if **any** critical task overdue.

---

## 11. Final Recommended Model

| Area | Model |
|------|--------|
| **Parent–child** | **Support Ticket** = case; **Support Task** = execution lines; **optional Project** for cross-ticket planning. |
| **Visibility** | **Customer:** ticket comments + **filtered** tasks (milestones / customer-action types); **internal:** full task list. |
| **Overdue / delay** | **Task-first** dates; **delay** fields for accountability; **ticket** aggregate for dashboards. |
| **Reporting** | **Task-level** operational reports; **ticket-level** summaries; **printable** plan from task list + Gantt. |
| **Mobile workflow** | Same statuses; **offline** later for **queue + submit**; **camera** for evidence; **push** for waiting and milestones. |

---

## 12. Open Questions / Optional Enhancements

| # | Question / enhancement |
|---|-------------------------|
| 1 | Add **explicit “Customer visible”** checkbox on **Support Task** for finer control than task_type alone. |
| 2 | Add **Waiting for Approval** to **Support Task** status options if approval gates are frequent at task level. |
| 3 | **Automated ticket** % from tasks — **weighted** by task type (e.g. Go Live = 30%). |
| 4 | **Task-level** customer-visible comments (child table) vs **ticket-only** comments. |
| 5 | **SLA** definitions: first response vs first milestone vs resolution — which tie to **ticket** vs **task** due dates. |
| 6 | **Reopen** rules: new ticket vs reopen same — affects reporting continuity. |

---

*This document confirms business rules only and does not constitute implementation. Align with your existing technical build specification for field names, workflows, and API contracts before development.*
