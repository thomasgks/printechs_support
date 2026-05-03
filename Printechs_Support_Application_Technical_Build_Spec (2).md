# Printechs Support Application – Technical Build Specification (Phase I)
**Target Platform:** ERPNext / Frappe  
**Purpose:** Detailed build specification for Cursor AI / developers  
**Phase:** Phase I – Software Division  
**Prepared for:** Printechs

---

## 1. Objective

Build a **Support Application inside ERPNext** for Printechs with the following key goals:

- Manage software support tickets through web and mobile-friendly ERPNext screens
- Link every support case to an ERPNext **Customer**
- Control entitlement, SLA, and validity through a custom **Support Agreement** DocType
- Track support and implementation work using **Support Tasks**
- Measure:
  - how many times a customer approached support
  - first response time
  - resolution time
  - customer-side vs Printechs-side delay
- Send and log all customer communication through the application email flow
- Provide daily / weekly / monthly task visibility
- Produce monthly management reporting

This Phase I must be designed so it can later expand to **Industrial** and **Retail** divisions.

---

## 2. Final Architecture

### 2.1 Core Model
- **Customer** = ERPNext standard master
- **Support Agreement** = support contract / SLA / validity / coverage master
- **Support Ticket** = main transactional document (issue / request / implementation case)
- **Support Task** = execution line / project plan item / follow-up task
- **Support Ticket Comment** = timeline log / communication log
- **Support SLA Template** = SLA rule master
- **Support Team** = ownership and assignment master
- **Support Ticket Type** = request classification master
- **Delay Reason** = standardized delay reporting master

### 2.2 Only custom field in Customer
Keep only:
- `support_portal_enabled` (Check)

Do **not** add division, SLA, agreement validity, AMC/PMC, contacts, or coverage logic to Customer.  
All such logic must remain in custom support DocTypes.

---

## 3. Functional Scope – Phase I

### Included
- Software support ticketing
- New implementation / project-type support case
- AMC-aware ticket eligibility
- Customer portal readiness
- Email-driven communication thread
- Internal team workflow
- Implementation task tracking
- Calendar-ready task structure
- Reminder-ready task structure
- Delay ownership analysis
- Reporting and KPI foundation

### Excluded in Phase I
- Industrial machine service process
- Retail machine service process
- Workshop repair
- Spare parts consumption
- Serial-number-based warranty tracking
- Field technician app for machine repair

---

## 4. Division Model

### Supported Divisions
- Software
- Industrial
- Retail

### Phase I Rule
Only **Software Division** will be active in actual workflow, but all custom DocTypes should still include `division` so the architecture is future-ready.

---

## 5. Customer Login and Portal Logic

### Rule
When customer logs in:
1. system identifies linked ERPNext Customer
2. system checks whether `support_portal_enabled = 1`
3. system checks active **Support Agreement** records
4. system auto-detects eligible division and support context
5. customer should not manually select division if system can determine it

### Future-ready logic
If multiple active agreements exist:
- system should try to auto-map using:
  - division
  - project
  - product
  - agreement type
- if ambiguity remains, controlled internal selection can be allowed

---

## 6. Main Build Decision

For **new implementation**, the application must support preparing the **project plan inside the application**.

### Design Rule
- One implementation = one **Support Ticket**
- Each implementation plan line = one **Support Task**

This means Support Task is both:
- a support action item
- a project plan task
- an implementation follow-up line
- a delay accountability line

### Required output views for project plan
1. **Normal / tabular view**
   - printable
   - exportable
   - suitable for customer documentation

2. **Graphical view**
   - Gantt/timeline-style
   - can be introduced after tabular version
   - recommended as Phase I.5 / Phase II enhancement if needed

---

## 7. Required DocTypes

Build the following DocTypes.

### 7.1 Support Agreement
**Type:** Main custom DocType  
**Purpose:** Stores support entitlement, SLA, validity, and division/project context.

#### Fields
| Label | Fieldname | Type | Notes |
|---|---|---|---|
| Agreement ID | naming_series | Select | Example `SUP-AGR-.YYYY.-.#####` |
| Customer | customer | Link | Customer |
| Customer Name | customer_name | Data | Fetch from customer |
| Division | division | Select | Software / Industrial / Retail |
| Agreement Type | agreement_type | Select | AMC / PMC / Warranty / New Implementation / Support Contract / Development Contract |
| Status | status | Select | Draft / Active / Expired / Suspended / Closed |
| Valid From | valid_from | Date | |
| Valid To | valid_to | Date | |
| Grace Period Days | grace_period_days | Int | |
| Default Priority | default_priority | Select | Low / Medium / High / Critical |
| Is Support Enabled | is_support_enabled | Check | |
| Allows Ticket Creation | allows_ticket_creation | Check | |
| Covers Bug Fixes | covers_bug_fixes | Check | |
| Covers User Support | covers_user_support | Check | |
| Covers Development | covers_development | Check | |
| Covers Remote Support | covers_remote_support | Check | |
| Covers Onsite Visit | covers_onsite_visit | Check | future use |
| Covers Training | covers_training | Check | |
| Covers Installation | covers_installation | Check | |
| Response SLA Hours | response_sla_hours | Float | |
| Resolution SLA Hours | resolution_sla_hours | Float | |
| Working Hours Only | working_hours_only | Check | |
| Is Billable After Expiry | is_billable_after_expiry | Check | |
| Max Tickets Per Month | max_tickets_per_month | Int | optional |
| Contract Value | contract_value | Currency | optional |
| Project | project | Link | Project, optional |
| Software Product | software_product | Link | Item or custom product master |
| Environment | environment | Select | Production / UAT / Test / Development |
| Implementation Date | implementation_date | Date | |
| Go Live Date | go_live_date | Date | |
| Primary Contact | primary_contact | Link | Contact |
| Support Email | support_email | Data | |
| Support Phone | support_phone | Data | |
| Auto Apply for Portal | auto_apply_for_portal | Check | |
| Portal Visible | portal_visible | Check | |
| Notes | notes | Text Editor | |

#### Suggested validations
- `valid_to >= valid_from`
- only active records with valid dates should be auto-linked
- if `division = Software`, software-specific fields may be shown
- if `status = Expired`, ticket linking should follow billable rules

---

### 7.2 Support Agreement Coverage Detail
**Type:** Child Table  
**Purpose:** Optional granular coverage override.

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Service Category | service_category | Data or Link |
| Is Covered | is_covered | Check |
| Remarks | remarks | Small Text |
| Response SLA Hours | response_sla_hours | Float |
| Resolution SLA Hours | resolution_sla_hours | Float |

---

### 7.3 Support Ticket Type
**Type:** Master

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Ticket Type Name | ticket_type_name | Data |
| Division | division | Select |
| Default Priority | default_priority | Select |
| Is Billable by Default | is_billable_by_default | Check |
| Requires Approval | requires_approval | Check |
| Default Team | default_team | Link |
| Default SLA Template | default_sla_template | Link |
| Is Active | is_active | Check |

### Recommended values for Software Division
- Incident
- Service Request
- Bug Fix
- Enhancement Request
- AMC Support Request
- Change Request / Development
- New Project Enquiry / Project Request
- New Implementation

---

### 7.4 Support Team
**Type:** Master

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Team Name | team_name | Data |
| Division | division | Select |
| Team Lead | team_lead | Link |
| Default Email | default_email | Data |
| Is Active | is_active | Check |

---

### 7.5 Support SLA Template
**Type:** Master

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Template Name | template_name | Data |
| Division | division | Select |
| Ticket Type | ticket_type | Link |
| Priority | priority | Select |
| First Response Hours | first_response_hours | Float |
| Resolution Hours | resolution_hours | Float |
| Working Hours Only | working_hours_only | Check |

---

### 7.6 Delay Reason
**Type:** Master  
**Purpose:** Standardize delay reporting.

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Reason Name | reason_name | Data |
| Reason Type | reason_type | Select |
| Description | description | Small Text |
| Is Active | is_active | Check |

### Recommended Reason Type values
- Printechs Delay
- Customer Delay
- Third Party Delay
- Shared Delay

### Example Delay Reasons
- Waiting for customer data
- Waiting for customer approval
- Waiting for UAT feedback
- Waiting for deployment window
- Waiting for Printechs development
- Internal resource unavailable
- Waiting for third-party vendor
- Waiting for infrastructure readiness

---

### 7.7 Support Ticket
**Type:** Main transactional DocType  
**Purpose:** Main support/request/project case.

#### Fields
| Label | Fieldname | Type | Notes |
|---|---|---|---|
| Ticket ID | naming_series | Select | Example `SUP-TKT-.YYYY.-.#####` |
| Customer | customer | Link | Customer |
| Customer Name | customer_name | Data | Fetch |
| Support Agreement | support_agreement | Link | Support Agreement |
| Division | division | Select | |
| Agreement Type | agreement_type | Data or Select | fetched from agreement |
| Channel | channel | Select | Portal / Email / Internal / Mobile |
| Ticket Type | ticket_type | Link | Support Ticket Type |
| Subject | subject | Data | |
| Description | description | Text Editor | |
| Priority | priority | Select | Low / Medium / High / Critical |
| Status | status | Select | workflow controlled |
| Opening Date | opening_date | Datetime | |
| Due Date | due_date | Datetime | |
| Contact Person | contact_person | Data or Link | |
| Contact Email | contact_email | Data | |
| Contact Mobile | contact_mobile | Data | |
| Project | project | Link | optional |
| Software Product | software_product | Link | |
| Environment Type | environment_type | Select | Production / UAT / Test / Development |
| Module Name | module_name | Data | |
| Version No | version_no | Data | |
| Reference Document Type | reference_document_type | Data | |
| Reference Document Name | reference_document_name | Data | |
| Is Under Contract | is_under_contract | Check | |
| Under AMC | under_amc | Check | |
| Is Billable | is_billable | Check | |
| Requires Approval | requires_approval | Check | |
| Quotation Required | quotation_required | Check | |
| Quotation | quotation | Link | optional |
| Assigned To | assigned_to | Link | User |
| Assigned By | assigned_by | Link | User |
| Assigned On | assigned_on | Datetime | |
| Team | team | Link | Support Team |
| Escalation Level | escalation_level | Int | |
| First Response Due | first_response_due | Datetime | |
| Resolution Due | resolution_due | Datetime | |
| First Response On | first_response_on | Datetime | |
| Resolved On | resolved_on | Datetime | |
| Closed On | closed_on | Datetime | |
| Is Overdue | is_overdue | Check | calculated |
| Response Time in Minutes | response_time_in_minutes | Float | calculated |
| Resolution Time in Minutes | resolution_time_in_minutes | Float | calculated |
| Customer Approach Count | customer_approach_count | Int | report or computed |
| Delay Owner | delay_owner | Select | None / Printechs / Customer / Third Party / Shared |
| Delay Reason | delay_reason | Link | Delay Reason |
| Delay Remarks | delay_remarks | Text | |
| Waiting For Side | waiting_for_side | Select | None / Printechs / Customer / Third Party |
| Waiting Since | waiting_since | Datetime | |
| Total Waiting Time Hours | total_waiting_time_hours | Float | calculated |
| Root Cause | root_cause | Small Text or Text | |
| Resolution Summary | resolution_summary | Text Editor | |
| Resolution Type | resolution_type | Select | Fixed / User Guidance / Configuration Change / Enhancement Logged / Duplicate / Cannot Reproduce / Moved to Project / Converted to Quote |
| Customer Confirmation Required | customer_confirmation_required | Check | |
| Customer Rating | customer_rating | Int or Rating | |
| Customer Feedback | customer_feedback | Small Text | |
| Is Reopened | is_reopened | Check | |
| Reopened Count | reopened_count | Int | |
| Source Email ID | source_email_id | Data | |
| Last Customer Update On | last_customer_update_on | Datetime | |
| Last Internal Update On | last_internal_update_on | Datetime | |

#### Recommended workflow statuses
- Draft
- Open
- Acknowledged
- In Progress
- Waiting for Customer
- Waiting for Internal Team
- Waiting for Approval
- Resolved
- Closed
- Cancelled
- Reopened

#### Recommended behaviors
- portal/email tickets can start at `Open`
- internal manual creation may start at `Draft`
- first internal action can set `Acknowledged`
- customer pending action should move to `Waiting for Customer`
- internal/development pending action should move to `Waiting for Internal Team`
- resolved tickets may close automatically after configurable period if customer does not reopen
- every reopen should increment `reopened_count`

---

### 7.8 Support Task
**Type:** Main transactional DocType  
**Purpose:** Task engine for support follow-up, implementation plan, customer-side action items, internal action items.

This DocType is critical.

#### Rule
A Support Ticket may have **many Support Tasks**.

#### Fields
| Label | Fieldname | Type | Notes |
|---|---|---|---|
| Task ID | naming_series | Select | Example `SUP-TSK-.YYYY.-.#####` |
| Support Ticket | support_ticket | Link | Support Ticket |
| Customer | customer | Link | fetch from ticket |
| Support Agreement | support_agreement | Link | fetch from ticket |
| Division | division | Select | fetch |
| Project | project | Link | optional |
| Subject | subject | Data | |
| Description | description | Text Editor | |
| Task Type | task_type | Select | Internal Task / Customer Action / Follow-up / Development / Testing / UAT / Training / Meeting / Implementation Step |
| Status | status | Select | Open / In Progress / Waiting for Customer / Waiting for Printechs / Completed / Cancelled / Delayed |
| Responsible Side | responsible_side | Select | Printechs / Customer / Shared |
| Assigned To User | assigned_to_user | Link | User |
| Assigned To Contact | assigned_to_contact | Link | Contact |
| Assigned Email | assigned_email | Data | |
| Planned Start Date | planned_start_date | Datetime | |
| Planned End Date | planned_end_date | Datetime | optional |
| Due Date | due_date | Datetime | |
| Actual Start Date | actual_start_date | Datetime | |
| Actual End Date | actual_end_date | Datetime | |
| Is Calendar Event | is_calendar_event | Check | |
| Send Email Reminder | send_email_reminder | Check | |
| Reminder Datetime | reminder_datetime | Datetime | |
| Is Delayed | is_delayed | Check | calculated/manual |
| Delay Owner | delay_owner | Select | Printechs / Customer / Third Party / Shared |
| Delay Reason | delay_reason | Link | Delay Reason |
| Delay Remarks | delay_remarks | Text | |
| Delay Days | delay_days | Float | calculated |
| Completion Notes | completion_notes | Text Editor | |
| Outcome | outcome | Small Text | |
| Evidence Attachment | evidence_attachment | Attach | |

#### Expected uses
- implementation project plan
- support follow-up list
- customer-side pending action list
- internal work plan
- calendar entries
- reminder engine source

#### Recommended behaviors
- if `responsible_side = Customer`, task can appear in customer pending-action view
- if `send_email_reminder = 1`, scheduled job should send reminder
- if overdue and not completed, mark delayed
- delay reason should be required when delayed
- internal and customer ownership must be visible in reports

---

### 7.9 Support Ticket Comment
**Type:** Child Table or separate DocType  
**Purpose:** timeline/history log.

#### Fields
| Label | Fieldname | Type |
|---|---|---|
| Parent Ticket | parent_ticket | Link |
| Comment Type | comment_type | Select |
| Comment By | comment_by | Link |
| Comment On | comment_on | Datetime |
| Content | content | Text Editor |
| Is Customer Visible | is_customer_visible | Check |
| Attachment | attachment | Attach |

### Comment Type values
- Internal Note
- Customer Reply
- Email
- System Update

---

## 8. Relationships

### 8.1 Relationship map
- Customer → many Support Agreements
- Customer → many Support Tickets
- Support Agreement → many Support Tickets
- Support Ticket → many Support Tasks
- Support Ticket → many Support Ticket Comments
- Support Ticket Type → used by Support Ticket
- Support Team → used by Support Ticket
- Support SLA Template → used by ticket type / agreement / ticket rule
- Delay Reason → used by Support Ticket and Support Task

---

## 9. Auto-Linking Logic for Support Agreement

When a ticket is created:
1. identify customer
2. fetch active Support Agreements:
   - same customer
   - `status = Active`
   - today between `valid_from` and `valid_to` (with grace rules if needed)
3. filter by division
4. if ticket contains project or product, prefer matching agreement
5. if only one suitable agreement exists, auto-link it
6. if none found:
   - mark ticket billable or pending manual review based on business rule
7. copy/inherit:
   - division
   - agreement_type
   - default priority if ticket priority blank
   - SLA values
   - covered/billable rules

---

## 10. SLA Logic

### 10.1 SLA source priority
Recommended evaluation order:
1. Support Agreement Coverage Detail override
2. Support Agreement values
3. Support Ticket Type linked SLA Template
4. Default fallback

### 10.2 Required calculations
On ticket creation:
- set `first_response_due`
- set `resolution_due`

On first official internal response:
- set `first_response_on`
- calculate `response_time_in_minutes`

On resolution:
- set `resolved_on`
- calculate `resolution_time_in_minutes`

### 10.3 Overdue logic
- `is_overdue = 1` if unresolved and now > resolution_due
- support dashboards must show overdue counts

---

## 11. Delay Tracking Logic

### 11.1 Ticket-level delay
Used for overall case-level reporting.

### 11.2 Task-level delay
Used for accurate responsibility tracking.

### 11.3 Delay ownership
Allowed values:
- Printechs
- Customer
- Third Party
- Shared

### 11.4 Waiting-side logic
At ticket and/or task level:
- `waiting_for_side`
- `waiting_since`

This supports:
- time pending with customer
- time pending with Printechs
- delay accountability reporting

### 11.5 Mandatory delay reason
Recommended rule:
- if task becomes delayed, require:
  - delay_owner
  - delay_reason
  - delay_remarks

---

## 12. Email Communication Requirements

All customer communication should happen through this application.

### 12.1 Required functions
- send acknowledgment on ticket creation
- send assignment or alert emails internally
- allow user reply from ticket screen
- capture incoming customer replies into same ticket
- store attachments received by email
- show full communication history in timeline

### 12.2 Important rules
- email subject must include ticket number
- incoming replies must map back to correct ticket
- internal notes must never be visible to customer
- customer-visible comments and email replies must be clearly flagged

### 12.3 Suggested email templates
- Ticket Acknowledgment
- Ticket Assigned
- Waiting for Customer
- Reminder for Pending Task
- Ticket Resolved
- Ticket Closed
- Implementation Task Reminder

---

## 13. Reminder and Notification Logic

### 13.1 Reminder sources
Use Support Task as the main reminder source.

### 13.2 Reminder targets
- assigned internal user
- customer-side responsible contact
- optional escalation manager

### 13.3 Reminder events
- before due date
- on due date
- overdue reminder
- repeated reminder for critical pending items

### 13.4 Suggested scheduled jobs
- daily morning reminder job
- hourly overdue scan job
- end-of-day summary job (optional)

---

## 14. Calendar Requirements

### 14.1 Views required
- Daily
- Weekly
- Monthly

### 14.2 Calendar entries should come from
- Support Task planned_start_date
- Support Task due_date
- reminder_datetime
- optional meeting tasks

### 14.3 Calendar filters
- by customer
- by project
- by engineer
- by responsible side
- by delayed/open/completed status

---

## 15. Portal and Mobile Requirements

### 15.1 Customer portal
Customer should be able to:
- log in
- view own tickets
- create ticket
- reply to ticket
- upload attachment
- see ticket history
- view own pending tasks / action items
- receive reminder emails

### 15.2 Internal web app
Internal team should be able to:
- view ticket queues
- filter by customer/project/status/priority/assigned user
- assign/reassign
- create tasks under tickets
- update ticket/task statuses
- reply by email
- add internal note
- open task calendar
- see overdue and delay dashboards

### 15.3 Mobile
Phase I can use:
- mobile-responsive ERPNext forms/pages
- or a lightweight portal/mobile UI later

At minimum internal users should be able to:
- view assigned tickets
- update ticket status
- add comment
- create/update tasks
- upload screenshots/photos
- check daily tasks

---

## 16. Workflow Recommendations

### 16.1 Ticket workflow
- Draft
- Open
- Acknowledged
- In Progress
- Waiting for Customer
- Waiting for Internal Team
- Waiting for Approval
- Resolved
- Closed
- Cancelled
- Reopened

### 16.2 Task workflow
- Open
- In Progress
- Waiting for Customer
- Waiting for Printechs
- Completed
- Cancelled
- Delayed

### 16.3 Suggested permissions
#### Customer
- view own tickets/tasks only
- add customer replies
- upload attachments

#### Support Coordinator
- create/assign/update tickets
- create tasks
- communicate with customer

#### Support Engineer
- update assigned tickets/tasks
- reply to customer
- add internal notes

#### Project Manager
- monitor implementation tickets/tasks
- delay review
- calendar oversight
- closure approval if required

#### Manager/Admin
- full view
- reporting
- SLA monitoring
- escalations
- close authority

---

## 17. Dashboard and Reporting Requirements

### 17.1 Dashboard widgets
- tickets opened this month
- tickets resolved this month
- overdue tickets
- tasks due today
- delayed tasks
- average first response time
- average resolution time
- top customers by ticket count
- tickets by status
- tasks by responsible side
- delay count by owner

### 17.2 Key reports
#### 1. Monthly Support Summary
- tickets opened
- tickets closed
- pending tickets
- average response time
- average resolution time

#### 2. Customer Support Frequency Report
- customer-wise ticket count
- reopen count
- repeated issue trend

#### 3. Delay Analysis Report
- delayed ticket/task
- delay owner
- delay reason
- delay days
- customer vs Printechs split

#### 4. Engineer Productivity Report
- assigned tickets
- completed tickets
- assigned tasks
- delayed tasks
- average response/resolution

#### 5. Implementation Progress Report
- ticket/project
- total tasks
- completed tasks
- pending tasks
- delayed tasks
- pending with customer
- pending with Printechs

#### 6. Printable Project Plan
Tabular format:
- task
- responsible side
- assigned person
- planned start
- due date
- actual completion
- status
- delay reason

### 17.3 Future enhancement
- graphical Gantt report for implementation ticket/tasks

---

## 18. Naming Series

Suggested:
- Support Agreement: `SUP-AGR-.YYYY.-.#####`
- Support Ticket: `SUP-TKT-.YYYY.-.#####`
- Support Task: `SUP-TSK-.YYYY.-.#####`

---

## 19. Suggested Frappe Build Notes

### 19.1 Use standard ERPNext/Frappe features where possible
- DocTypes
- Workflows
- Assignments
- Auto Email Reports
- Notification
- Portal view
- Calendar view
- Script Reports / Query Reports

### 19.2 Expected custom logic
- agreement auto-matching
- SLA due date calculation
- first response / resolution time calculation
- delay and waiting-side calculation
- email reply mapping
- reminder scheduler
- customer-side pending task visibility

### 19.3 Suggested implementation order
1. Masters
   - Support Ticket Type
   - Support Team
   - Support SLA Template
   - Delay Reason
2. Support Agreement
3. Support Ticket
4. Support Task
5. Support Ticket Comment / timeline
6. Workflow & permissions
7. Email integration
8. Reports
9. Portal
10. Calendar/reminders

---

## 20. Suggested API / Server-Side Methods

Create server-side methods for:

### Agreement
- get_active_support_agreement(customer, division=None, project=None, software_product=None)
- validate_support_agreement(doc)

### Ticket
- auto_link_support_agreement(doc)
- apply_sla_to_ticket(doc)
- mark_first_response(ticket)
- resolve_ticket(ticket, resolution_summary)
- reopen_ticket(ticket)

### Task
- create_task_from_ticket(ticket, values)
- mark_task_delayed(task)
- send_task_reminder(task)
- get_customer_pending_tasks(customer)

### Reports / scheduled jobs
- update_overdue_flags()
- send_daily_task_reminders()
- build_monthly_support_summary()
- build_delay_analysis_snapshot()

---

## 21. Technical Notes for Cursor AI

Use this build approach:

### Backend
- Frappe DocTypes + Python controllers
- use hooks, validate, before_save, on_update, scheduled jobs where appropriate

### Frontend
- ERPNext/Frappe forms
- list views
- workspace/dashboard
- reports
- portal pages
- mobile-responsive forms

### Keep in mind
- do not overload Customer master
- Support Task is the main engine for implementation tracking
- all communication history must remain traceable
- design for future Industrial/Retail expansion
- keep DocTypes normalized and reusable

---

## 22. Open Business Assumptions Used in This Spec

These assumptions were used while preparing this build spec:

1. Only `support_portal_enabled` stays in Customer
2. One customer may have multiple Support Agreements
3. One implementation case can be represented by one Support Ticket
4. One implementation plan line is one Support Task
5. Tabular project plan is mandatory
6. Graphical/Gantt project plan is desirable and can be phased
7. Delay ownership is required for accountability
8. Email is the primary communication channel in Phase I

If business decisions change, update the rules before coding.

---

## 23. Final Recommendation

Proceed with development in this order:
1. finalize business rules
2. build DocTypes
3. configure workflows and permissions
4. implement ticket-task-agreement logic
5. implement email and reminder flow
6. build reporting
7. build customer portal screens
8. refine UI/wireframes

This specification is intended to be directly usable as a development instruction file for Cursor AI and the implementation team.
