# PRAI Studio

Internal Frappe Desk module for uploading Modern POS source code, analyzing it, running ERPNext health checks, generating draft FAQs and Help Articles, reviewing them, and publishing approved knowledge to the live PRAI Agent.

## Access

- **Desk only** — no customer portal access to source uploads, analysis, or draft content.
- **Roles**
  - `PRAI Studio Developer` — upload, scan, analyze, generate drafts, run health checks
  - `PRAI Studio Manager` — full Studio access including review and publish
  - `Printechs Support Coordinator` — full Studio access including review and publish
  - `Printechs Support Engineer` — read/review scan runs and knowledge runs
  - `Support Team` — read-only

## Workflow

### Phase 1 — Upload & scan

1. Create **PRAI Source Project** and attach a `.zip` file (max **200 MB**).
2. Click **Extract and Scan Source**.

### Phase 2 — Analyze, FAQ draft, review, publish

1. **Create Knowledge Run** from an extracted scan run.
2. **Run Source Analysis** → analyzer findings.
3. **Generate Draft Content** → draft FAQs (+ Help Articles if enabled).
4. **Submit for Review** → manager **Approve Selected** / **Reject Selected**.
5. **Publish Approved to PRAI** → live **PRAI FAQ** records + **PRAI Publish Log**.

### Phase 3 — Health checks, Help Articles, richer analysis

1. **Run Health Checks** on a knowledge run (promotion not on POS, status mismatch, usage limits).
2. **Generate Draft Content** also creates **Draft Help Articles** (group guides + doc/API topics + health findings).
3. Approve and publish Help Articles to live **Help Center** (`status = Published`, portal-visible).
4. Publish package JSON (v2) includes both `faqs` and `help_articles`.
5. Richer C# analysis detects namespaces, interfaces, API routes, UI controls, and service patterns.

## Health rule templates

| Rule | Checks |
|------|--------|
| `promotion_not_on_pos` | Active promotions not available on Modern POS |
| `promotion_inactive_status` | Is Active but Status not Active/Approved |
| `promotion_usage_limit_reached` | Promotions at max usage |

Manage templates under **PRAI Studio → Health Rule Templates**.

## Install / migrate

```bash
bench --site <site> migrate
bench --site <site> clear-cache
```

## Tests

```bash
bench --site <site> run-tests --app printechs_support --module printechs_support.tests.test_prai_studio
bench --site <site> run-tests --app printechs_support --module printechs_support.tests.test_prai_studio_phase2
bench --site <site> run-tests --app printechs_support --module printechs_support.tests.test_prai_studio_phase3
```

Live PRAI chat uses published **PRAI FAQ** (`is_active = 1`) and **Help Article** (`status = Published`, portal-visible).
