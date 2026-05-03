# System Capability Review & Business Process Confirmation

**Document type:** Pre-development confirmation — business analysis only  
**Version:** 1.0  
**Scope:** Printechs Support (`Support Ticket`, `Support Task`, portal, reports)  
**Exclusions:** No code, APIs, migrations, or technical implementation in this document  

---

## 1. Executive Summary

Your ERPNext application implements a **strong Ticket → Task** structure that **matches** the intended business process for **project-style and additional development** work: one **Support Ticket** as the main case, many **Support Tasks** as execution lines, with **dates, assignees, delay ownership, SLA-style fields on the ticket**, and **rich task-level scheduling and delay fields**.

**What is already well supported in the data model**

- Parent case + execution plan (**Support Task** requires **Support Ticket**).
- Manager/self-assignment via **Ticket Assignees** + **Assigned To (Primary)** and audit fields (**Assigned By**, **Assigned On**).
- Per-task **planned/actual dates**, **due date**, **reminders**, **status**, **responsible side**, **delay reason/owner/remarks**, **completion notes**, **evidence attachment**.
- Ticket-level **delay** and **waiting** context (**delay_owner**, **waiting_for_side**, **waiting_since**, etc.) and **customer-visible comment** rows with **Is Customer Visible**.
- **Version history** on key documents (**track_changes** on Support Ticket and Support Task).

**Gaps to resolve before treating the solution as “complete” for customer discretion and management analytics**

1. **Customer visibility of tasks:** The **recommended** model is to show **milestones and customer-relevant tasks only**. The current **portal task list** exposes the **same task fields to customer-scoped users as to internal users** (all tasks under their tickets), **without** a per-task “customer visible” flag or server-side filtering by task type. This is a **business/process gap** relative to “customer should not see every internal technical activity.”
2. **Ticket vs task automation:** The model **supports** aligning ticket status with task state (e.g. **Waiting for Customer**, **Waiting for Approval**), but **automatic** promotion (e.g. “one task waiting → ticket waits”) is a **process/automation decision**—not implied solely by static DocTypes. Confirm rules and implement consistently (Desk + portal + mobile).
3. **Reporting depth:** Standard reports found include **Open Support Tickets** and **Overdue Support Tickets** (ticket grain). **Task-level** management reports (engineer load, delayed tasks by owner, implementation progress) are **expected to be available via Query/Script reports or workspace**—confirm which are **built and published** for production use.
4. **Overdue vs delayed semantics:** Fields exist (**is_overdue** on ticket; **due_date**, **Delayed** status, **is_delayed** on task). **Business rules** for when to set **Delayed** vs leave **overdue as calculated**, and mandatory **delay reason**, must be **confirmed and enforced in process** (and optionally in validation later).

**Conclusion (one line):** The **structural** design is **fit for purpose**; **mobile development can proceed** in parallel with **confirming visibility rules, automation rules, and report inventory** so behavior matches the agreed customer and management experience.

---

## 2. Business Scenario Confirmation

| Step | Business need | System support |
|------|----------------|----------------|
| Customer creates ticket | Intake | **Support Ticket** with customer, type, priority, description; portal and Desk paths exist in app scope |
| Manager assigns to technician or self | Ownership | **Ticket Assignees** (table), **Assigned To**, **Assigned By/On**, **Team** |
| Technician creates multiple tasks under ticket | Execution plan | **Support Task** with mandatory **support_ticket** link |
| Track delivery, delay, accountability | Operations | Ticket + task dates, delay fields, comments, metrics fields |
| Customer sees progress without full internal detail | Communication | **Support Ticket Comment** with **Is Customer Visible**; **gap** on selective task visibility (see §6) |

The **Vehicle Tracking** scenario (one enhancement ticket, seven logical steps) maps **naturally** to **one ticket + seven tasks**. That is the **recommended final pattern** for implementation-style work.

---

## 3. Ticket → Task Model Confirmation

### 3.1 Recommended structure (confirmed)

| Principle | Confirmation |
|-----------|--------------|
| One **Support Ticket** = one main case / request | **Yes** — aligns with DocType purpose and linking |
| Many **Support Tasks** = execution steps | **Yes** — `support_ticket` is required on Support Task |
| Task list = project plan inside ticket | **Yes** — best practice for development/enhancement work |
| Each task has own dates, owner, status, remarks | **Yes** — fields exist (assignees, schedule, status, description, completion_notes, etc.) |
| Overall ticket progress derived from children | **Recommended** — derive via rule (e.g. count completed / total or weighted by type). **project_plan_progress** on task supports % when linked to project plan; otherwise define a simple roll-up rule |

### 3.2 Optional linkage

- **Project** on ticket/task supports **ERPNext Project** and Gantt-style planning when needed; not mandatory for every ticket.

**Verdict:** The **Ticket → Task** model is **appropriate and sufficient** as the core design for project-style support and additional development.

---

## 4. Task Date and Overdue Tracking Confirmation

### 4.1 Fields present on Support Task (reviewed)

| Business need | Field(s) in design |
|---------------|-------------------|
| Planned start / end | **planned_start_date**, **planned_end_date** |
| Due date | **due_date** |
| Actual start / end | **actual_start_date**, **actual_end_date** |
| Reminder | **send_email_reminder**, **reminder_datetime** |
| Completion | **completion_notes**, **outcome**, **evidence_attachment** |
| Delay | **is_delayed**, **delay_owner** (Printechs / Customer / Third Party / Shared), **delay_reason** (link), **delay_remarks**, **delay_days** (read-only, system-maintained per design) |

### 4.2 How dates should be used (business flow)

- **Planned** dates = planning and Gantt; **Due** = operational commitment for **overdue** checks.
- **Actual** dates = record of what happened for **audit** and **dispute** review.

### 4.3 Overdue vs delayed — definitions

| Term | Recommended meaning |
|------|---------------------|
| **Overdue** | **Time-based**: current time is past **due_date** (task) or past ticket **resolution_due** / **due_date** (ticket), and the item is **not** in a terminal state. **Should be system-calculated** in reports (and ticket **is_overdue** where your logic maintains it). |
| **Delayed** | **Business acknowledgment**: work is **off track** or blocked in a way that needs **ownership** and **reason** — use status **Delayed** and/or **is_delayed** plus **delay_owner** and **delay_reason** / remarks. **Requires user confirmation** (and reason) when you adopt a strict policy. |

**Difference:** Overdue = **calendar/SLA** signal; Delayed = **managed exception** with accountability.

### 4.4 Ticket-level overdue

- **Support Ticket** includes **is_overdue** (read-only), **resolution_due**, **first_response_due**, etc. — supports **management** view of case-level SLA.

**Verdict:** **Data model supports** the required distinction; **policies** must be fixed in writing (who marks Delayed, when reason is mandatory).

---

## 5. Progress Update and Daily Follow-up Confirmation

### 5.1 What the system can capture per task

| Need | Mechanism |
|------|-----------|
| Status | **status** (Open, In Progress, Waiting for Customer, Waiting for Printechs, Completed, Cancelled, Delayed) |
| Internal detail | **description** (Text Editor); **track_changes** on document |
| Completion | **completion_notes**, **outcome**, **evidence_attachment** |
| Customer-facing narrative | **Not** on task row by default — use **ticket comments** (customer-visible) for customer story |

### 5.2 Daily follow-up — recommended model

- **Internal:** Update **task status** + short **description** or notes; use **Delayed** fields when slipping.
- **Customer:** Add **Support Ticket Comment** with **Is Customer Visible** = yes — **required** for a clear customer timeline **without** exposing every internal line.

### 5.3 Is task history alone enough?

- **For internal dispute and engineering audit:** **Task document history** (Frappe **Version**) + **owner/modified** metadata + **comments on ticket** for customer-facing commitments.
- **For customer trust:** **Ticket-level** customer-visible comments **are required** in addition to task records.

**Verdict:** **Use both** — tasks for **execution truth**; **ticket comments** for **customer-visible** communication.

---

## 6. Customer Visibility Confirmation

### 6.1 Recommended final model (business)

| Layer | What customer sees |
|-------|---------------------|
| **Ticket** | Subject, status, high-level dates (as you expose), **customer-visible** comments and attachments |
| **Tasks** | **Only** tasks that are **milestones**, **customer actions**, **UAT/go-live**, or explicitly marked visible — **or** summarized progress (“5 of 7 milestones complete”) |

### 6.2 Current system behavior vs recommendation

| Topic | Data model | Portal behavior (capability review) |
|-------|------------|-------------------------------------|
| Ticket comments | **Is Customer Visible** on **Support Ticket Comment** | **Supported** — API filters non-visible rows for customer users |
| Task list for customer | No **customer_visible** field on **Support Task** | **Portal lists all tasks** for the customer’s tickets with **full task field set** returned for customer-scoped users — **does not match** “hide internal technical tasks” without **process** (only use milestone types) or **future** field + filter |

**Practical interim (no schema change):** Use **task_type** convention (e.g. only **Customer Action**, **UAT**, **Implementation Step** for customer-relevant lines) and **train** users; **UI/mobile** should **filter** by policy. **Stronger:** add a **Customer Visible** checkbox on **Support Task** and enforce in portal/mobile.

### 6.3 Notifications (business expectations)

| Event | Recommendation |
|-------|----------------|
| Approval needed | Ticket **Waiting for Approval** + customer-visible comment; optional notification channel |
| Waiting for customer | Task/ticket **Waiting for Customer** + comment |
| Milestone / go-live | Customer-visible comment or visible milestone task |
| Delay | Customer-visible summary if customer-facing impact |

**Verdict:** **Model is sound**; **gap** = **selective task visibility** in customer channels — **confirm rule** and align **portal/mobile** behavior before claiming full compliance.

---

## 7. Status Flow Confirmation

### 7.1 Task status changes (meanings)

| Situation | Task handling |
|-----------|----------------|
| In progress | **In Progress**; set **actual_start_date** when policy says |
| Completed | **Completed**; **actual_end_date**, **completion_notes** |
| Waiting on customer | **Waiting for Customer** |
| Internal dependency | **Waiting for Printechs** |
| Slipping | **Delayed** + delay fields |

### 7.2 Ticket status changes (meanings)

| Situation | Ticket handling |
|-----------|----------------|
| Active work | **In Progress** (or **Acknowledged** per your SOP) |
| Customer blocking | **Waiting for Customer** |
| Internal blocking | **Waiting for Internal Team** |
| Approval gate | **Waiting for Approval** |
| Done | **Resolved** → **Closed** |

### 7.3 Cross-level rules (recommended defaults)

| Question | Recommended answer |
|----------|---------------------|
| One task **Waiting for Customer** — must ticket move? | **Often yes** when **no other** work can proceed; if other tasks run in parallel, ticket can stay **In Progress**. **Decide per workflow** and apply consistently. |
| All tasks completed — auto **Resolved**? | **Recommended** as optional automation or **checklist** before manager sets **Resolved**. |
| One task delayed — ticket shows risk? | **Recommended:** ticket **delay** section or **flag** derived from **any** open delayed/overdue critical task — **report/dashboard** level if not on document. |

**Verdict:** **Statuses exist** on both levels; **coordination rules** are **business** + **optional automation** — confirm SOP.

---

## 8. Reporting and Monitoring Confirmation

### 8.1 What the platform can support

- **ERPNext reporting** on **Support Ticket** and **Support Task** (Query/Script reports, workspace shortcuts).
- Existing **Overdue Support Tickets** report: **ticket** grain, uses **is_overdue**, **resolution_due**.

### 8.2 Management reports — purpose and fields

| Report | Purpose | Key fields | Grain |
|--------|---------|------------|-------|
| Tasks per ticket | Workload | Ticket, counts by status | Ticket |
| Completed / pending / overdue / delayed tasks | Execution control | Task, assignee, due, delay_owner | Task |
| Engineer load | Capacity | Assignee, open task count | User / Task |
| Pending approvals | Gate tracking | Ticket status, **requires_approval** | Ticket |
| Implementation progress | PM view | Completed vs total tasks, dates | Ticket |
| Printable plan | Stakeholder | Task list + dates + owners | Ticket + Task |
| Delay history | Dispute | delay_reason, delay_owner, dates | Task + Ticket |

**Verdict:** **Data is reportable**; **confirm** which reports are **already authored** in ERPNext vs **still to be built** for go-live.

### 8.3 Customer-facing “reports”

- **Current status, milestones, pending actions, history** = **portal ticket view** + **visible tasks** + **comments** — not necessarily a separate PDF.

---

## 9. History and Accountability Confirmation

| Requirement | Support in Frappe / your design |
|-------------|----------------------------------|
| Who created/updated task | **Owner**, **modified**, **modified_by**; **Version** history (**track_changes** on Support Task) |
| When started / delayed / completed | **actual_start_date**, **actual_end_date**, **status** changes in versions |
| Why delayed | **delay_reason**, **delay_remarks**, **delay_owner** |
| Who approved | **Approval** often **ticket-level** (**Waiting for Approval** + comments); **task-level** approval can be recorded in **completion_notes** or comment — **confirm** if formal approver field needed |
| Customer responded | **Support Ticket Comment** (**Customer Reply**); **last_customer_update_on** on ticket |
| Resolved/closed | **resolved_on**, **closed_on**, **resolution_summary** |

**Verdict:** **Strong** accountability for **ticket** and **task**; **formal approver** on task may need **explicit** field if audits require it beyond comments.

---

## 10. Worked Example — Vehicle Tracking Ticket

| Phase | What happens | Who sees what |
|-------|----------------|---------------|
| Create | Customer opens ticket “Vehicle Tracking module”; type enhancement | Customer: ticket created |
| Assign | Manager assigns **Ali** (or self); status **In Progress** | All: assignee visible on ticket |
| Tasks | Ali creates 7 tasks with **due dates** | Internal: full list; Customer: **currently all 7 in portal list** — **refine visibility** per §6 |
| Progress | Tasks move **In Progress** → **Completed** | Internal: task board; Customer: **comments** + **filtered** tasks (recommended) |
| Wait customer | Task 4 **Waiting for Customer**; ticket may **Waiting for Customer** | Customer: comment + pending action |
| Delay | Task 5 **Delayed**, **delay_owner** = Printechs, **delay_reason** set | Manager: delay report; Customer: **summary** via visible comment (recommended) |
| Complete | Tasks 1–7 **Completed** | Ticket → **Resolved** / **Closed** |
| Reports | Export task history, version log | Management / dispute |

---

## 11. Final Gap Analysis Before Further Development

| # | Gap | Severity | Mitigation (business-first) |
|---|-----|----------|-----------------------------|
| 1 | Customer may see **all** tasks in portal API | **High** for privacy/UX | Define **visibility rule**; filter in UI/API by **task_type** or add **Customer Visible** field |
| 2 | Ticket/task status **sync** not automatic | **Medium** | Document SOP; add automation later if needed |
| 3 | Task-level **“Waiting for Approval”** status | **Low** — ticket has **Waiting for Approval** | Use ticket + comment; or extend task options |
| 4 | **Task-level** reports not all listed as standard | **Medium** | Build report pack for go-live |
| 5 | **Formal approver** on task | **Low** | Use comments / ticket until audit requires field |

---

## 12. Final Recommendation and Confirmation

### 12.1 Direct answers

1. **Is Ticket → Task sufficient for project-style and additional development?**  
   **Yes.** The structure matches the process; optional **Project** link adds enterprise planning when needed.

2. **Mandatory missing features before mobile?**  
   **No blocking schema gap** for mobile **if** you accept: (a) **visibility rules** implemented in mobile + portal per §6, (b) **SOP** for status alignment, (c) **report pack** plan. The **main** gap is **customer task visibility policy**, not absence of tasks.

3. **Fields / controls / rules to confirm now**  
   - **Customer task visibility** (filter vs new field).  
   - **When ticket** must be **Waiting for Customer** vs parallel work.  
   - **When delay reason is mandatory**.  
   - **Roll-up** formula for ticket **% complete**.  
   - **Which reports** are mandatory for management go-live.

4. **Can we proceed to mobile development?**  
   **Yes**, in parallel with **finalizing** the above business rules; mobile should **mirror** the same permissions and visibility as portal.

### 12.2 Single closing statement

Your **Support Ticket System** already provides the **right bones** for **delivery control, delay accountability, and audit**; **confirm customer-facing task exposure and operational playbooks**, then proceed with **mobile** aligned to those rules.

---

*End of document — pre-development confirmation only.*
