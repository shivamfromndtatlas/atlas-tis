# NDT Atlas Talent Intelligence System (TIS)
## Architecture and Initial Development Specification

| | |
|---|---|
| **Version** | 1.0 (baseline for Sprint 0) |
| **Date** | 24 November 2026 |
| **Stack** | React + TypeScript + Material UI · Python / Django + DRF · MySQL 8 · Redis · Celery · Django Channels |
| **Reference system** | AtlasHiring "Command Centre" v3 (Node + SQLite, Oct 2026) — reviewed for stages, parameters and lessons learned |
| **Status** | Ready for stakeholder sign-off. Items marked **[DECIDE]** need an owner decision before the sprint that builds them (§22) |

---

## 0. How to read this document

1. §1–2: confirmed decisions and what we take from AtlasHiring.
2. §3–11: functional specification (who can do what, and how every requested feature works).
3. §12–19: technical architecture (stack, data model, API, security, integrations, ops).
4. §20–22: development plan, risks and open decisions.

Appendix A traces every one of the 13 original requirements to the section that covers it.

---

## 1. Scope and confirmed decisions

TIS is NDT Atlas's in-house, end-to-end recruitment platform: requisition → job posting → multi-channel sourcing → application → automated + human screening → assessments → interviews → client decision → offer → joining → 90-day handholding, with every user type working in one portal and candidates seeing their own progress in real time.

| Decision | Confirmed value | What it means in this spec |
|---|---|---|
| Organisation structure | **Single** | One deployment, one operating organisation (NDT Atlas). Client companies are records inside it, not separate tenants. NDT Atlas's own internal hiring is modelled as a client marked `is_internal = true` (AtlasHiring's "Hiring For → ATLAS / Client AEIS" switch). Data isolation between clients is enforced by row-level scoping (§3.3), not separate databases. |
| Candidate registration | **Both** | (a) Auto sign-up when applying through a job link, and (b) standalone registration on the careers portal to join the talent pool without applying. A third path — recruiter/consultant-created profiles — sends the candidate a "claim your profile" invite. |
| Client recruiter access | **Full** | Client users see everything about *their own company's* jobs: full candidate profiles, resumes, contact details, assessment results, scorecards and history. They can give feedback, schedule and run client interviews, record decisions and raise new requisitions. They never see other clients' data or Atlas-internal notes marked private. |
| Resume screening | **Hybrid** | Deterministic knock-out rules + configurable weighted scoring + AI semantic fit analysis, combined into an explainable score. A human confirms the outcome; auto-reject is opt-in per job and limited to hard knock-outs (§6). |
| Integrations | Email, WhatsApp, Google Calendar, Criteria assessments | All behind a provider abstraction with delivery logs, retries and admin-visible health (§10). |
| Workflow | AtlasHiring stages as the default, **configurable** | A workflow-template engine; the AtlasHiring process ships as template "Atlas Standard v1" (§5). |

### 1.1 Out of scope for v1 (candidates for v2)
Payroll/HRMS onboarding, consultant invoicing and payouts, job-board API posting (Naukri/LinkedIn multi-posting — v1 uses share links and manual posting), mobile native apps (v1 is a responsive PWA), video interviewing inside TIS (we use Google Meet links), background-verification vendor integration, multilingual UI (built i18n-ready, English only at launch).

---

## 2. What we take from AtlasHiring

AtlasHiring v3 was reviewed in full (code, migrations, seed data, admin guide, implementation report). It is a working single-server ATS with real recruitment content, but it was not designed for the scale, user types or integrations TIS needs.

### 2.1 Carried over (business rules and parameters)

| From AtlasHiring | Becomes in TIS |
|---|---|
| 12-step current process (Requirement from U.S. → … → 90-day handholding) plus Offer / Joined / Closed tracking | Default workflow template "Atlas Standard v1" (§5.2) |
| **Human review gates** — Criteria review requires approved criteria + assessment, video and proctoring review + linked evidence before downstream progression | Stage gates with mandatory checklists (§5.3). Nothing is auto-passed on test scores. |
| "Do not use Talent Signal alone as a pass rule; review proctoring flags manually; thresholds are inferred, not approved" | Criteria scores are shown against *reference ranges* only after HR approves them per job; never an automatic pass/fail (§10.4) |
| "Acceptance alone does not count as joining" | Offer and Joining are separate records with separate dates (§8.6) |
| Handholding milestones: Week-1 touch point, guidance & training, Day-30 expectation alignment, 90-day handholding | Post-hire milestone checklist with reminders (§5.2, §8.6) |
| Targets: feedback within hours, offer within 24 h, hire in 5–7 days (proposed) | Per-stage SLA fields in the template, initially **unset** until HR baselines them |
| Potential duplicates are flagged, **never auto-merged**; one person can have many applications | Duplicate detection with manual, audited merge (§8.5) |
| Missing scores stay blank, never zero; missing dates stay unknown | Nullable scores/dates throughout; analytics exclude nulls rather than treating them as zero |
| Position fields: entity, department, standardised title, level, category, vacancy status, approved headcount, open requisitions, strategic criticality (A-position), primary sourcing channel, location, hiring manager, target SLA | Job / requisition model (§13) |
| JD fields: key accountabilities, core competencies (BARS / McClelland), version, approval status | JD document + structured competencies on the job; drives BEI scorecards |
| Partner metrics: submissions, qualified-shortlist %, offer-to-join yield %, commercial terms & SLA | Consultant agency model and consultant dashboard KPIs |
| Criteria attempt fields: CCAT raw/percentile, EPP, WPP, Emotify score ranges met, Excel percentile, Talent Signal, invalid flags, 8 proctoring signals | `AssessmentResult` schema (§13) |
| Scorecards: competency definitions, weights totalling 100, blank ratings stay null, no automatic hiring decision | Scorecard templates and interview feedback (§8.4) |
| Document versioning, soft archive, SHA-256 integrity, PDF/DOCX preview | File service (§12.5) |
| Audit of every change; role change invalidates sessions | Audit log + session revocation (§15) |
| 12 clickable KPI drilldowns, source conversions with application denominators, ageing, feedback turnaround, follow-up views (My actions, Today, Upcoming, Waiting, Overdue) | Recruiter dashboard and analytics (§11) |

### 2.2 Gaps in AtlasHiring that TIS must close

| AtlasHiring limitation | TIS approach |
|---|---|
| Whole workspace stored as one JSON blob in a SQLite row; single server, no replicas | Normalised MySQL schema; stateless app servers; horizontal scale |
| 30-second polling for updates | WebSockets (Django Channels) with real-time push |
| No email, WhatsApp, calendar, Criteria, Naukri integrations | Email, WhatsApp, Google Calendar, Criteria integrations (§10) |
| No candidate-facing portal, no public job pages | Careers portal, shareable job links, candidate dashboard |
| Stages hard-coded | Configurable workflow templates |
| No DOC conversion, OCR, malware scanning | LibreOffice conversion, OCR fallback, antivirus scan (§12.5) |
| No MFA, no password reset | MFA for staff, OTP/magic link for candidates, self-service reset |
| JSON-typed scorecards | Row-based scorecard editor |
| Manual backups only | Automated backups with point-in-time recovery |
| Agency label spelling had to match source text ("White Force" vs "WhiteForce", "StartBoard" vs "StratBoard Search") | Agencies are master records with IDs; free-text labels never drive permissions |

---

## 3. Users, roles and permissions

### 3.1 Roles

| Role code | Who | Summary of rights |
|---|---|---|
| `SUPER_ADMIN` | NDT Atlas system owners | Everything. User and role CRUD, permission matrix, client CRUD, workflow templates, screening defaults, notification templates, integrations, audit, data exports, retention jobs. |
| `ATLAS_RECRUITER` | NDT Atlas recruiters | Post/edit/publish jobs, upload JDs, assign jobs to Atlas recruiters and consultants, manage all applications on jobs they own or are assigned to, run screening, move stages, schedule interviews, record feedback, manage offers/joining/handholding. |
| `ATLAS_LEAD` *(permission set on top of ATLAS_RECRUITER)* | Recruitment managers / HR heads | All Atlas jobs (not only assigned), approve requisitions and offers, approve Criteria reference ranges, reassign work, team analytics. |
| `CLIENT_USER` | Recruiter / POC at a client company | **Full** access to their own client's jobs and applicants (§1). Raise requisitions, review submitted profiles, give feedback, schedule/run client interviews, record decisions, view their client dashboard. |
| `CONSULTANT` | External recruiter / consultant (individual or belonging to an agency) | Sees only jobs assigned to them (or their agency). Submits candidates, sees and updates only the candidates they own, sees stage progress of their submissions, receives feedback marked "share with consultant". |
| `CANDIDATE` | Job seeker | Own profile, applications, assessments, interviews, offers, notifications, documents. |
| *(v1.1)* `INTERVIEWER` | Panel member without recruiter rights | Sees only applications where they are on the interview panel; submits scorecards. |

A user has exactly one *primary* role; `ATLAS_LEAD` and future capabilities are granted as permission sets. Super Admin can create **custom roles** by cloning a base role and toggling permissions in the matrix (requirement 7, "assigning rights").

### 3.2 Permission matrix (defaults — editable by Super Admin)

Legend: ✅ full · 🔸 own/assigned/scoped only · 👁 read only · ❌ none

| Capability | Super Admin | Atlas Recruiter | Atlas Lead | Client User | Consultant | Candidate |
|---|---|---|---|---|---|---|
| Users & roles CRUD | ✅ | ❌ | 🔸 (invite client/consultant users) | 🔸 (invite colleagues of own client, **[DECIDE]**) | ❌ | ❌ |
| Client CRUD | ✅ | 👁 | ✅ | 👁 own | ❌ | ❌ |
| Requisition create | ✅ | ✅ | ✅ | 🔸 own client | ❌ | ❌ |
| Requisition approve | ✅ | ❌ | ✅ | 🔸 own client (client-side approval step) | ❌ | ❌ |
| Job publish / unpublish | ✅ | 🔸 owned/assigned | ✅ | ❌ (**[DECIDE]**, flag `client_can_publish`) | ❌ | ❌ |
| Assign job to recruiters/consultants | ✅ | 🔸 jobs they own | ✅ | ❌ | ❌ | ❌ |
| Generate share links | ✅ | ✅ | ✅ | 🔸 own client jobs | 🔸 assigned jobs (tagged to them) | ❌ |
| View applications | ✅ | 🔸 assigned jobs | ✅ | 🔸 own client jobs (all sources) | 🔸 own submissions | 🔸 own |
| Candidate contact details | ✅ | ✅ | ✅ | ✅ (full access) | 🔸 own submissions | own |
| Move stage | ✅ | 🔸 | ✅ | 🔸 stages flagged `client_actionable` (client interview, decision) | ❌ (request only) | ❌ (withdraw only) |
| Internal notes (Atlas-private) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Shared feedback | ✅ | ✅ | ✅ | ✅ | 👁 where shared | 👁 where shared |
| Screening config per job | ✅ | 🔸 | ✅ | 👁 | ❌ | ❌ |
| Offers (create/approve) | ✅ | 🔸 create | ✅ approve | 🔸 approve own client (**[DECIDE]**) | 👁 own submissions | 🔸 accept/decline own |
| Workflow templates | ✅ | 👁 | ✅ | ❌ | ❌ | ❌ |
| Notification templates & integrations | ✅ | ❌ | 👁 | ❌ | ❌ | ❌ |
| Audit log | ✅ | 🔸 records they can see | ✅ | ❌ | ❌ | ❌ |
| Bulk export | ✅ | 🔸 (logged) | ✅ (logged) | 🔸 own client (logged) | ❌ | 🔸 own data (DPDP access request) |

### 3.3 How access is enforced
Three layers, all server-side (the UI only hides what the API already refuses):

1. **Permission check** — DRF permission classes read the role/permission-set matrix (cached in Redis, invalidated on change).
2. **Row scoping** — every queryset goes through a `ScopedQuerySet.for_user(user)` manager:
   - Client user → `job.client_id = user.client_id`
   - Consultant → `job ∈ assignments(user or user.agency)` **and** `application.owner_consultant ∈ (user, agency)`
   - Atlas recruiter → owned/assigned jobs (lead: all)
   - Candidate → `candidate.user_id = user.id`
3. **Field redaction** — serializers drop fields the role may not see (e.g. Atlas-private notes, expected CTC to consultants if configured, other consultants' identities).

Automated tests assert each role × endpoint × scope combination (§18).

---

## 4. Functional module map

| # | Module | Covers requirement |
|---|---|---|
| M1 | Identity, roles & permissions | 1, 7 |
| M2 | Client management | 2 |
| M3 | Requisitions & job posting (form + JD upload) | 3, 12 |
| M4 | Job assignment (Atlas recruiters, consultants) | 3 |
| M5 | Careers portal, shareable job links & source tracking | 4, 8 |
| M6 | Candidate registration, apply & auto sign-up | 5 |
| M7 | Candidate profile & completeness meter | 6 |
| M8 | Resume parsing & hybrid screening engine | 9 |
| M9 | Configurable workflow & pipeline (Kanban, gates) | 11, 13 |
| M10 | Interviews, scorecards & feedback | 11 |
| M11 | Assessments (Criteria) | 13, integrations |
| M12 | Offers, joining & 90-day handholding | 13 |
| M13 | Notifications & real-time updates | 11, integrations |
| M14 | Dashboards & analytics | 10 |
| M15 | Administration, audit, data governance | 7 |
| M16 | AtlasHiring data migration | 13 |

---

## 5. Configurable recruitment workflow (M9)

### 5.1 Engine design
- A **WorkflowTemplate** is a versioned, ordered list of **Stages**. Super Admin / Atlas Lead edit templates in a visual editor (drag to reorder, add, rename, archive).
- When a job is published it **pins a template version**. Editing a template later never silently changes live jobs; an admin can migrate a job to a newer version through a stage-mapping wizard that maps every old stage to a new one and logs the move.
- Each stage has these configurable properties:

| Property | Purpose |
|---|---|
| `key`, `name` | Internal identifier and recruiter-facing name |
| `candidate_label` | What the candidate sees (e.g. internal "Criteria + proctored video" → candidate "Online assessment"). Supports transparency without exposing internal detail. |
| `category` | `screening`, `assessment`, `interview`, `client`, `offer`, `post_hire`, `terminal`, `parking` — drives analytics and dashboard grouping |
| `order`, `is_optional` | Sequence; optional stages can be skipped with a reason |
| `entry_gate` | Checklist/evidence required **before** a candidate can enter (e.g. Simulation requires the assessment gate to be passed) |
| `exit_gate` | Checklist/evidence required to leave forward |
| `required_scorecard_template` | Forces a scorecard before exit |
| `allowed_actor_roles` | Who may move candidates into/out of this stage (e.g. `client_actionable`) |
| `sla_hours` | Optional; drives ageing, overdue flags, escalations |
| `on_enter_actions` | Automations: send notification template(s), create Criteria invite, open scheduling, create task, notify client |
| `visible_to_client`, `visible_to_consultant`, `visible_to_candidate` | Visibility of the stage and its history per audience |
| `allowed_transitions` | Default: next stage, any terminal, any previous stage (backwards moves require a reason) |

- Every move writes a `StageTransition` row (from, to, actor, timestamp, reason, gate evidence snapshot) — the full history AtlasHiring kept as `stageHistory`, now relational.

### 5.2 Default template "Atlas Standard v1" (from AtlasHiring)

**Requisition lifecycle (job-level, AtlasHiring stages 1–2):**
`Requirement received` → `JD drafting` → `Pending approval` → `Approved` → `Published / Sourcing` → `On hold` → `Filled` / `Closed` / `Cancelled`.
AtlasHiring's "Requirement from the U.S." becomes the requisition's *origin* field (client + requesting manager), not a candidate stage.

**Application pipeline (candidate-level):**

| # | Key | Recruiter name | AtlasHiring ref | Candidate label | Category | Gate / rules |
|---|---|---|---|---|---|---|
| 1 | `applied` | Applied | (new) | Application received | screening | Automatic on apply; triggers screening |
| 2 | `screening` | Applications, screening & filtering | 3 | Under review | screening | Hybrid screening result must be reviewed by a human before exit (unless job enables auto-advance for "Strong fit") |
| 3 | `verbal_connect` | Verbal connect — basic questions | 4 | Recruiter call | screening | Call notes / question set completed |
| 4 | `shortlist` | Shortlisting | 5 | Shortlisted | screening | Shortlist reason |
| 5 | `assessment` | Criteria test + proctored video (mandatory) | 6 | Online assessment | assessment | On enter: Criteria invite. **Exit gate:** criteria settings approved for the job, assessment reviewed, video reviewed, proctoring reviewed, evidence reference, reviewer name |
| 6 | `simulation` | Simulation | 7 | Work simulation | assessment | **Entry gate:** stage-5 gate passed |
| 7 | `bei_interview` | BEI & situational interview | 8 | Interview | interview | BEI scorecard (competencies from JD) required |
| 8 | `client_submission` | Pass to client | 9 | Profile shared with hiring team | client | Submission summary; client notified |
| 9 | `client_interview` | Client interview (Atlas HR observes silently) | 10 | Final interview | client | `client_actionable`; Atlas observer recorded on the interview |
| 10 | `client_decision` | Client decision | 11 | Decision in progress | client | `client_actionable`; decision + reason |
| 11 | `offer` | Offer | Offer tracking | Offer | offer | Sub-status: drafted → approved → released → accepted / declined / expired. SLA field ready for "offer within 24 h" once approved |
| 12 | `joined` | Joined | Joined tracking | Joined | post_hire | Actual joining date required (acceptance ≠ joining) |
| 13 | `handholding` | 90-day handholding | 12 | Onboarding support | post_hire | Milestones: Week-1 touch point, Guidance & training, Day-30 expectation alignment, Day-90 completion |
| — | `on_hold` | On hold | — | Under review | parking | Returns to previous stage |
| — | `rejected` | Rejected | Closed | Not progressing | terminal | Reason code + stage at rejection; candidate message template |
| — | `withdrawn` | Withdrawn | Closed | Withdrawn | terminal | By candidate or recruiter |
| — | `dropped` | Dropped / no-show | Stage 7 legacy | Closed | terminal | Reason |

> Note: AtlasHiring numbers 90-day handholding (12) before its Offer/Joined tracking rows. TIS orders them logically (Offer → Joined → Handholding); confirm with HR in Sprint 0.

The AtlasHiring "intended" process (Source → Screen → Recruiter call → HR round → Criteria then simulation → BEI/situational + client interview → Offer within 24 h) is shipped as a second, inactive template "Atlas Fast-track (proposed)" so HR can trial it on selected jobs.

### 5.3 Gates and evidence
Gates are checklists defined on the stage: each item is `boolean`, `text`, `file`, `link`, `scorecard`, or `assessment_review`. A move that fails a gate returns `409 GATE_NOT_SATISFIED` with the missing items, and the UI opens the checklist drawer. Super Admin can grant a **gate override** permission; overrides require a reason and are flagged on the application and in audit.

### 5.4 Kanban and list views
- Per-job Kanban (dnd-kit), columns = stages, cards show score band, source, days-in-stage (red when SLA breached), owner, next action.
- Bulk actions: move, reject with template, send message, assign owner, export.
- Cross-job pipeline view for recruiters, filters: client, job, stage, source, owner, consultant, score band, date ranges, SLA status.

---

## 6. Hybrid resume screening (M8)

### 6.1 Pipeline
```
Resume upload ─► virus scan ─► text extraction ─► AI structured parsing ─► candidate profile (prefill)
                                                        │
Job screening config ───────────────────────────────────┤
                                                        ▼
                              L1 knock-outs ─► L2 weighted rules score ─► L3 AI fit analysis
                                                        │
                                                        ▼
                         Composite score + band + reasons ─► recruiter review ─► stage action
```
Runs asynchronously in Celery (target < 60 s per resume, bulk queues for re-screens).

### 6.2 Layer 1 — Knock-out rules (deterministic)
Configured per job (defaults copied from a screening profile):
- Minimum / maximum total experience
- Location / willingness to relocate / work mode
- Notice period ≤ N days
- Expected CTC ≤ budget ceiling (or within band)
- Mandatory qualifications / certifications (e.g. CPA for Accounts)
- Must-have skills (with synonym lists)
- Knock-out screening questions answered on the apply form (yes/no, numeric, choice)
- Work authorisation / shift availability

Result per rule: `pass`, `fail`, or `unknown` (data missing). **Unknown never equals fail** — it sends the application to "Needs review".

### 6.3 Layer 2 — Weighted rules score (0–100)
Factors with weights that must total 100 (validated): must-have skills coverage, good-to-have skills, experience band fit, relevant-domain experience, education, location fit, notice period fit, CTC fit, tenure stability, screening-question scores. Each factor emits a sub-score and a human-readable reason.

### 6.4 Layer 3 — AI fit analysis (advisory)
- Uses the Claude API (official `anthropic` Python SDK) with **structured outputs** (Pydantic schema via `client.messages.parse`) to return: fit score 0–100, matched requirements with evidence quotes from the resume, gaps/concerns, suggested verbal-connect questions, and a confidence level.
- **Bias controls:** before the fit call, the resume text is redacted of name, gender, age/DOB, photo, marital status, religion, caste, nationality and address; the AI is given the JD requirements and the redacted experience only.
- Model ID is a setting (`TIS_AI_MODEL`, default `claude-opus-5-5`); prompt template version and model ID are stored with every result for audit and reproducibility. Refusals and errors fall back to "AI unavailable" and the composite uses L1+L2 only.
- Bulk re-screening (e.g. after a recruiter edits the job criteria) uses the Message Batches API at reduced cost.
- Before AI scoring is switched on for live jobs, a labelled evaluation set (~100 historical resumes with recruiter decisions) is built and agreement is measured (§18).
- **[DECIDE]** Data-processing approval for sending (redacted) resume text to an external AI provider; DPDP notice wording covers it (§15.3).

### 6.5 Composite, bands and actions
`composite = w_rules × L2 + w_ai × L3` (default 60 / 40, configurable per job; any L1 fail caps the band at "Not a fit").

| Band | Default rule | Default action |
|---|---|---|
| Strong fit | composite ≥ 75, no knock-out fails | Suggest → Verbal connect (optional auto-advance per job) |
| Potential fit | 50–74 | Recruiter review queue |
| Needs review | any `unknown` knock-out or AI unavailable | Recruiter review queue, flagged |
| Not a fit | composite < 50 or any knock-out fail | Suggest reject. **Auto-reject only if the job enables it, only for hard knock-outs, after a configurable hold (default 24 h) during which a recruiter can override** |

Every score screen shows *why* (rule results, factor reasons, AI evidence). Recruiters can override the band with a reason; overrides feed the evaluation set.

### 6.6 Re-screening triggers
Job criteria changed; candidate updates profile/resume; manual "re-screen". History of all screening runs is retained.

---

## 7. Jobs, JD upload, assignment and share links (M3, M4, M5)

### 7.1 Requisition and job
A **Requisition** (the need) and a **JobPosting** (what is published) are one record with a lifecycle (§5.2) to keep v1 simple; a requisition can have headcount > 1 and tracks filled count.

Fields (from AtlasHiring + requirements): client, entity/hub, department, standardised title, level, category (current vacancy / pipeline / critical), strategic criticality (A/B/C), priority, approved headcount, open positions, location(s), work mode, employment type, experience range, CTC budget band (private to Atlas + client), skills (must/good), qualifications, key accountabilities, competencies (BARS/McClelland — feed BEI scorecard), hiring manager, target SLA days, target start date, workflow template, screening profile, screening questions, application form options (resume required?), visibility (public / unlisted link-only / internal), owner recruiter, JD document(s), success profile document(s), approval record.

### 7.2 Posting by form or by JD upload (requirement 12)
1. **Form:** multi-step MUI form (Basics → Requirements → Screening → Workflow → Team & assignment → Preview & publish). Draft autosave.
2. **JD upload:** drop a `.pdf`, `.docx` or `.doc` → file stored and versioned → text extracted (pdfplumber / python-docx; `.doc` via headless LibreOffice; scanned PDF via OCR) → AI structured extraction into the job schema → the same form opens **pre-filled**, each AI-filled field marked "auto-filled — please verify" → recruiter edits and publishes. The original JD stays attached, downloadable, and shown on the public page if chosen.

### 7.3 Approval and publish
Configurable: requisition approval by Atlas Lead and/or client user before publish. Publishing generates the canonical public URL and slug and makes the job visible on the careers portal (unless unlisted).

### 7.4 Assignment (requirement 3)
- `JobAssignment(job, assignee_user | agency, role_on_job ∈ {owner, co-recruiter, consultant}, assigned_by, start, end, target_submissions, commercial_terms_ref)`.
- Consultants/agencies see only assigned jobs; assignment and unassignment notify them.
- **Candidate ownership for consultants:** a consultant submission creates `CandidateOwnership(candidate, job, consultant, valid_until)` (default 90 days, configurable). If the candidate already exists (applied directly, or another consultant owns them for this job), the submission is flagged as an **ownership conflict** for an Atlas recruiter to resolve. Standard agency-recruiting practice; prevents double claims.

### 7.5 Unique shareable links (requirement 4)
- Canonical job URL: `https://<careers-domain>/jobs/<JOB-CODE>-<slug>`.
- **Tracked share links:** any permitted user generates `https://<careers-domain>/j/<shortcode>`; the shortcode records `job, created_by, channel (LinkedIn, Facebook, WhatsApp, Naukri, …), campaign, consultant (if any)`. Redirects to the canonical page with UTM parameters and sets a first-party attribution cookie (30 days).
- One-click share buttons (LinkedIn, Facebook, X, WhatsApp, email, copy link, QR code download for posters/job fairs).
- **Social previews:** the SPA cannot give crawlers per-job meta tags, so Django serves `/jobs/*` HTML with Open Graph / Twitter Card tags and **schema.org `JobPosting` JSON-LD** (Google for Jobs), then the React app hydrates. Also `sitemap.xml` and `robots.txt`.
- Click analytics per link (count, unique, apply conversion) in recruiter and consultant dashboards.
- Closed jobs keep their URL alive and show "No longer accepting applications" with similar open jobs.

### 7.6 Source capture (requirement 8)
The apply form **always asks** "Where did you hear about this job?" (required dropdown), pre-selected from the share link's channel when known, editable by the candidate.
Source master list (admin-configurable): LinkedIn, Naukri, Indeed, Facebook, Instagram, WhatsApp, X (Twitter), Company website / careers page, Employee referral (→ referrer name/employee ID), Consultant / agency (→ select), Campus / institute, Job fair / walk-in, Newspaper / print, Other (→ text).
Stored separately: `declared_source` (what the candidate chose), `link_channel`, `link_shortcode`, `utm_*`, `http_referrer_domain`, `owner_consultant`. Analytics use declared source by default with a toggle to tracked source, so mismatches are visible.

---

## 8. Candidate experience (M6, M7, M10, M12)

### 8.1 Apply with automatic sign-up (requirement 5)
Mobile-first, two short steps:
1. **Basic details:** full name, email, mobile (country code, validated with `phonenumbers`), current city, total experience, source (§7.6), resume upload (required/optional per job), job-specific screening questions, consents (privacy notice — required; WhatsApp updates — optional opt-in).
2. **Verify:** 6-digit OTP to email (and/or WhatsApp/SMS when enabled). Verification creates the account (passwordless), logs the candidate in, and submits the application.

Rules:
- If the email or mobile already belongs to an account → "Welcome back — verify to continue"; the application attaches to the existing profile (no duplicate account).
- Applying twice to the same job is blocked; the candidate is sent to their existing application.
- Bot protection: rate limiting per IP/email/mobile and an invisible challenge widget on the form.
- After submit: confirmation screen with the application tracker, the completeness meter and "complete your profile" prompts. Resume parsing pre-fills the profile; the candidate confirms the parsed data.
- Candidates can later set a password, or keep using OTP / magic-link login.

### 8.2 Standalone registration (decision "both")
`/register` on the careers portal: same basic fields + OTP; candidate joins the talent pool, can set job alerts (role, location, experience) and apply later with one click. Recruiter/consultant-created profiles send a "claim your profile" invite link; until claimed, the profile is marked `unclaimed` and the candidate receives only transactional messages they consented to.

### 8.3 Profile completeness meter (requirement 6)
Computed server-side on every profile change and stored (`profile_completeness`, `completeness_breakdown`). Sections and weights are admin-configurable; defaults:

| Section | Weight | Complete when |
|---|---|---|
| Basic details | 10 | Name, DOB (optional, not used in screening), gender (optional), current city |
| Verified contact | 10 | Email and mobile verified |
| Resume | 15 | At least one resume uploaded and parsed |
| Headline & summary | 5 | Both filled |
| Work experience | 15 | ≥1 entry with title, company, dates (or "fresher" declared) |
| Education | 10 | Highest qualification with institute and year |
| Skills | 10 | ≥5 skills |
| Job preferences | 10 | Expected CTC, notice period, preferred locations, work mode |
| Current compensation | 5 | Current CTC (or "not applicable") |
| Photo | 5 | Uploaded |
| Online profiles | 5 | LinkedIn or portfolio URL |
| **Total** | **100** | |

UI: circular progress with colour bands (<40 red, 40–79 amber, ≥80 green), a checklist of missing items with a one-tap link to each, and nudges (in-app + email/WhatsApp at day 2 and day 7 when < 60%, opt-out respected). Recruiters see the same percentage on candidate cards.

### 8.4 Application tracker and transparency (requirement 11)
Candidate dashboard → each application shows:
- A stepper of **candidate-visible stages** using `candidate_label`, with dates reached and the current stage highlighted.
- "What happens next" text per stage (template-configurable).
- Upcoming items: assessment link and deadline, interview date/time/Meet link with "Add to calendar", documents requested.
- **Feedback shared with candidate:** recruiters write feedback in two separate fields — *internal notes* (never shown) and *message to candidate* (shown and notified). Scorecards and internal ratings are never shown to candidates.
- Real-time: updates appear instantly over WebSocket, with email/WhatsApp per the notification matrix.
- Withdraw application (with optional reason).

### 8.5 Duplicates and identity
Normalised email and E.164 mobile are unique per account. A background job flags *potential* duplicates (same name + similar phone, fuzzy name + same DOB, same resume hash) for recruiter review. Merge is manual, previews field conflicts, keeps all applications and history, and is audited. No automatic merging (AtlasHiring rule).

### 8.6 Interviews, scorecards, offers, joining, handholding
- **Interviews:** type (verbal connect, BEI, situational, simulation, client), panel, observer (Atlas HR silent observer in client interviews), mode (Google Meet / phone / in-person), timezone-aware schedule (stored UTC + display timezone — Atlas hires for U.S. clients from India), Google Calendar event, reminders, reschedule/cancel, no-show.
- **Scorecards:** row-based editor (competency, definition, BARS anchors, weight); weights must total 100; blank ratings stay null; weighted score shown only when all weights are rated; recommendation (strong yes … strong no) + evidence. No automatic hiring decision.
- **Feedback turnaround:** each panel member has a feedback-due time; overdue feedback appears in dashboards and triggers reminders.
- **Offers:** offer record (CTC breakdown, joining date, designation, location, letter file), approval chain (Atlas Lead, optional client), release via email with secure link; candidate accepts/declines in portal (e-acceptance with timestamp and IP).
- **Joining:** actual joining date recorded separately from acceptance; no-show handling.
- **90-day handholding:** milestone tasks auto-created on joining (Week-1, Guidance & training, Day-30, Day-90), assigned to the owner recruiter, with reminders and notes; completion closes the application as "Hired — retained 90 days" (a key quality metric for clients and consultants).

---

## 9. Real-time updates and notifications (M13)

### 9.1 Event bus
Domain actions emit events (`application.stage_changed`, `interview.scheduled`, `feedback.shared`, `assessment.completed`, `offer.released`, …) through a single `publish_event()` service. Handlers (Celery) fan out to: in-app notifications, WebSocket push, email, WhatsApp, Google Calendar, audit, analytics counters. Transactional-outbox pattern (`OutboxEvent` table written in the same DB transaction, relayed by a worker) guarantees no event is lost if a worker is down.

### 9.2 Channels
- **In-app:** notification centre (bell, unread count, mark read), live via WebSocket; toasts for the active user.
- **Email:** HTML templates (MJML-compiled) with plain-text fallback; tracked delivery/bounce via provider webhooks.
- **WhatsApp:** only for users who opted in; only Meta-approved templates for business-initiated messages; delivery/read receipts via webhook; opt-out keyword (STOP) honoured.
- Every user has notification preferences per category and channel; transactional messages that are legally/operationally required (OTP, offer) cannot be disabled.

### 9.3 Default notification matrix

| Event | Candidate | Atlas recruiter | Client user | Consultant |
|---|---|---|---|---|
| Application submitted | Email + WA + in-app | In-app (digest option) | — | In-app (own submissions) |
| Screening complete (strong fit) | — | In-app | — | — |
| Stage changed (candidate-visible) | Email + WA + in-app | — | In-app (client stages) | In-app + email |
| Assessment invite / reminder | Email + WA | — | — | In-app |
| Assessment completed | In-app | In-app + email | In-app | In-app |
| Interview scheduled / rescheduled / cancelled | Email + WA + calendar invite | Calendar + in-app | Calendar + email | In-app |
| Interview reminder (24 h, 1 h) | WA + email | In-app | Email | — |
| Feedback due / overdue | — | In-app + email | Email | — |
| Profile shared with client | — | — | Email + in-app | In-app |
| Client decision recorded | Candidate-safe message | In-app + email | — | In-app |
| Offer released / accepted / declined | Email + WA | Email + in-app | Email | In-app |
| Job assigned to me | — | Email + in-app | — | Email + in-app |
| SLA breach | — | In-app + daily digest | Daily digest | — |
| Profile completeness nudge | Email/WA (opt-in) | — | — | — |

All templates are editable by Super Admin (subject, body, variables like `{{candidate.first_name}}`, `{{job.title}}`, `{{stage.candidate_label}}`, `{{interview.meet_link}}`), with preview and test-send.

---

## 10. Integrations

All integrations implement a provider interface (`send()`, `health()`, `handle_webhook()`), store credentials encrypted in the database (Super Admin UI) or in the secrets manager, log every call (`IntegrationLog`), retry with exponential backoff, and surface failures on the Super Admin dashboard.

### 10.1 Email
- Provider-agnostic via `django-anymail` (works with Amazon SES, SendGrid, Mailgun, Postmark …) or SMTP (e.g. Microsoft 365 / Google Workspace relay). **[DECIDE]** provider.
- Sending domain with SPF, DKIM and DMARC configured in Sprint 0 (deliverability of OTPs and offers depends on this).
- Bounce/complaint webhooks mark addresses as undeliverable and alert the recruiter.

### 10.2 WhatsApp
- WhatsApp Business Platform — either Meta's Cloud API directly or an Indian BSP (Gupshup, Interakt, Kaleyra, etc.). **[DECIDE]**. The adapter keeps the choice swappable.
- Lead times: Meta business verification and template approval can take days to weeks — start in Sprint 0.
- Templates needed at launch (≈10): OTP, application received, stage update, assessment invite, assessment reminder, interview scheduled, interview reminder, interview rescheduled/cancelled, offer released, profile nudge.
- Two-way: inbound candidate replies appear in the application's communication log for the recruiter (v1: read and reply within the 24-hour service window; v1.1: full inbox).

### 10.3 Google Calendar
- Each Atlas recruiter (and optionally client users) connects their Google account through OAuth 2.0 (Calendar events scope). If NDT Atlas runs Google Workspace, a domain-wide-delegated service account is the simpler alternative. **[DECIDE]**
- Scheduling: free/busy lookup across panel members → suggested slots → event created on the organiser's calendar with a **Google Meet link**, attendees (candidate, panel, client POC, silent observer), description with candidate profile link (internal attendees only).
- Changes in TIS update/cancel the event; event changes made in Google are synced back through push notifications (watch channels) or periodic sync.
- v1.1: candidate self-scheduling page (pick from offered slots).
- Candidates without Google still get the `.ics` invite by email.

### 10.4 Criteria assessments
- Per job, an Atlas Lead maps the job to the Criteria assessment configuration (tests: CCAT, EPP, WPP, Emotify, Excel; proctoring and video interview settings) and records the **approved reference ranges** (AtlasHiring flagged its thresholds as inferred and unapproved).
- On entering the `assessment` stage: TIS requests a candidate invite through the Criteria integration and sends the link by email/WhatsApp; status is tracked (invited, started, completed, expired).
- Results (scores, percentiles, score ranges met, invalid flags, Talent Signal, proctoring signals: face throughout session, face match, multiple people, mobile phone, voices, loss of recording, locked out) are stored in `AssessmentResult` with the raw payload.
- **The integration never moves the stage.** The recruiter completes the exit-gate checklist (criteria approved, assessment reviewed, video reviewed, proctoring reviewed, evidence, reviewer).
- **Access/API:** Criteria's ATS-integration access, endpoints and webhook/callback model must be confirmed with the Criteria account team in Sprint 0. A **CSV/XLSX import** of Criteria results (the format AtlasHiring already handles, matched by normalised email then name, never auto-selecting among ambiguous attempts) is built first so the stage works on day one regardless.

### 10.5 AI provider (screening and JD/resume parsing)
Claude API via the official `anthropic` Python SDK, called only from Celery workers (never from the browser), with structured outputs, timeouts, retries, refusal handling, per-call cost logging and a monthly budget alert. Disabling AI in settings leaves screening on L1+L2 rules and parsing on manual entry — the system keeps working.

---

## 11. Dashboards (M14 — requirement 10)

Built as responsive "bento grid" layouts of cards; every KPI tile drills down to the filtered list behind it (AtlasHiring's 12-drilldown pattern). Shared filters: date range, client, job, recruiter, source.

| Dashboard | Key widgets |
|---|---|
| **Super Admin** | Users by role & active sessions; jobs/applications volume; integration health (failed emails/WhatsApp, calendar token expiry, Criteria sync, AI cost vs budget); queue/backlog; audit feed; security events (failed logins, MFA resets); data-rights requests |
| **Atlas Recruiter** | My actions (Today / Upcoming / Waiting / Overdue — from AtlasHiring), my jobs with pipeline counts, screening review queue, interviews today, feedback overdue, offers pending, joiners this month, handholding milestones due, my share links' clicks → applies |
| **Atlas Lead** | Funnel by client/job, time-to-fill vs target SLA, time-in-stage and ageing, stage conversion, source effectiveness (applications → shortlist → offer → join, with application denominators), consultant performance (submissions, qualified-shortlist %, offer-to-join yield %, 90-day retention), recruiter workload, SLA breaches, offer acceptance rate |
| **Client User** | Open positions & headcount filled, pipeline per job, profiles awaiting my review, my upcoming interviews, decisions pending, feedback I owe, hires and 90-day status |
| **Consultant** | Assigned jobs and targets, my submissions by stage, conversion rates, ownership conflicts, feedback received, link performance |
| **Candidate** | Completeness meter, application trackers, upcoming assessments/interviews, offer actions, recommended jobs, notifications |

Reports: CSV/XLSX export (permission-checked and logged), scheduled email reports (weekly lead summary, client weekly pipeline).
Analytics are computed from transactional tables via indexed queries plus nightly-refreshed summary tables (`analytics_*`) for heavy aggregates.

---

## 12. System architecture

### 12.1 Style
A **modular monolith**: one Django project with clearly bounded apps, one React SPA, asynchronous workers. This fits the team size and a single-organisation deployment; module boundaries (services + events) leave room to extract services later.

```
                        ┌──────────────── Browser / Mobile (PWA) ────────────────┐
                        │ React SPA (MUI)       Public job pages (SSR meta + SPA) │
                        └───────────────┬───────────────────────┬────────────────┘
                                        │ HTTPS (REST)          │ WSS
                                  ┌─────▼───────────────────────▼─────┐
                                  │   Reverse proxy / CDN / WAF       │
                                  └─────┬───────────────────────┬─────┘
                          ┌─────────────▼─────────┐   ┌─────────▼──────────┐
                          │ Django (DRF) API      │   │ Django Channels    │
                          │ gunicorn+uvicorn (ASGI)│   │ (WebSocket)        │
                          └───┬─────────┬─────────┘   └─────────┬──────────┘
                              │         │ enqueue / outbox       │ pub/sub
                    ┌─────────▼──┐  ┌───▼──────────────┐   ┌─────▼─────┐
                    │ MySQL 8    │  │ Celery workers    │◄─►│  Redis    │
                    │ (primary + │  │ parsing, screening│   │ broker,   │
                    │  replica)  │  │ notifications,    │   │ cache,    │
                    └────────────┘  │ sync, analytics   │   │ channels  │
                                    └───┬──────────┬────┘   └───────────┘
                     ┌──────────────────┘          └───────────────────────┐
              ┌──────▼───────┐                                    ┌────────▼────────────┐
              │ Object store │  resumes, JDs, offer letters        │ External services   │
              │ (S3-compat.) │  (private, signed URLs, AV scan)    │ Email · WhatsApp ·  │
              └──────────────┘                                    │ Google Calendar ·   │
                                                                  │ Criteria · Claude   │
                                                                  └─────────────────────┘
```

### 12.2 Backend stack
| Concern | Choice |
|---|---|
| Language / framework | Python 3.12+, Django 5.2 LTS, Django REST Framework |
| API docs | drf-spectacular (OpenAPI 3) → generated TypeScript client for the frontend |
| Auth | Custom `User` model (email login); SimpleJWT in **httpOnly, Secure, SameSite cookies** (short-lived access + rotating refresh), CSRF protection; OTP via `pyotp`; TOTP MFA for staff (`django-otp`) |
| Real-time | Django Channels + `channels-redis`, served by an ASGI server |
| Async jobs | Celery + Redis broker; `django-celery-beat` for schedules (reminders, SLA checks, nudges, sync, retention) |
| Database | MySQL 8.0/8.4 LTS, InnoDB, `utf8mb4` / `utf8mb4_0900_ai_ci`, `mysqlclient` driver |
| Files | `django-storages` (S3-compatible; local/MinIO in dev); ClamAV scan; `pdfplumber`, `python-docx`, headless LibreOffice for `.doc`, Tesseract OCR fallback |
| Search | MySQL FULLTEXT (ngram parser) on resume/profile text for v1; OpenSearch only if volume requires (v2) |
| Matching helpers | `rapidfuzz` (skills/name fuzzy match), `phonenumbers` |
| AI | `anthropic` SDK + Pydantic schemas |
| Google | `google-api-python-client`, `google-auth-oauthlib` |
| Email | `django-anymail` + MJML templates |
| Quality | ruff, mypy (django-stubs), pytest-django, factory_boy, coverage |
| Observability | structlog JSON logs, Sentry, Prometheus metrics endpoint, health checks |

### 12.3 Frontend stack
| Concern | Choice |
|---|---|
| Core | React 18+ with TypeScript, Vite |
| UI | Material UI (MUI) latest stable + MUI X (Data Grid, Date/Time Pickers, Charts) |
| Routing | React Router (data routers, lazy-loaded role areas) |
| Server state | TanStack Query (caching, optimistic updates; WebSocket events invalidate queries) |
| Client state | Zustand (UI state only) |
| Forms | React Hook Form + Zod schemas |
| Drag & drop | dnd-kit (Kanban, stage editor, scorecard rows) |
| Uploads | react-dropzone with progress, chunked upload for large files |
| Feedback | notistack (snackbars), skeleton loaders |
| Motion | Framer Motion (subtle) |
| i18n | i18next (English at launch) |
| Tests | Vitest + React Testing Library; Playwright end-to-end |
| PWA | Service worker for candidate portal (installable, offline shell, push-ready) |

### 12.4 Design language ("latest trending patterns", applied with restraint)
- **Design tokens** in a single MUI theme (light + dark mode, NDT Atlas brand colours), 8-px spacing grid, 12–16 px radii, soft layered shadows.
- **Bento-grid dashboards** with drill-down cards; sparklines in KPI tiles.
- **Command palette** (Ctrl/⌘ + K) for staff: jump to candidate, job, action.
- **Master–detail drawers**: open a candidate from any list in a right-side drawer without losing context.
- Light **glassmorphism** only on hero/header surfaces of the public careers site; content surfaces stay solid for legibility.
- Skeleton loading, optimistic UI, meaningful empty states, micro-interactions on stage moves.
- **Mobile-first candidate portal** (most applicants arrive from social links on phones): sticky apply button, two-step apply, large touch targets.
- Accessibility: WCAG 2.2 AA (contrast checks on both themes, keyboard Kanban alternative, focus management, ARIA labels).
- A Storybook-style component catalogue for shared components.

### 12.5 File service
Upload → MIME sniff + extension allow-list (pdf, doc, docx, txt, jpg, png) → size limit (resumes 10 MB, JDs/offers 20 MB) → SHA-256 → antivirus scan → private object storage → `Document` + `DocumentVersion` rows. Access only through short-lived signed URLs issued after a permission check; every download is logged. Versions retained; archive is soft. PDF preview inline; DOCX preview via converted PDF.

### 12.6 Repository layout (monorepo)
```
atlas-tis/
├─ backend/
│  ├─ config/                 # settings (base/dev/staging/prod), urls, asgi, celery
│  ├─ apps/
│  │  ├─ core/                # base models (UUID, timestamps, soft delete), utils, permissions
│  │  ├─ accounts/            # User, roles, permission sets, OTP, MFA, sessions
│  │  ├─ clients/             # Client, ClientContact, Agency
│  │  ├─ jobs/                # Requisition/Job, assignments, share links, JD parsing
│  │  ├─ workflow/            # templates, stages, gates, transitions engine
│  │  ├─ candidates/          # profile, experience, education, skills, completeness, dedupe
│  │  ├─ applications/        # Application, stage history, notes, ownership, tasks
│  │  ├─ screening/           # rules, scoring, AI analysis, runs
│  │  ├─ assessments/         # Criteria config, invites, results, imports
│  │  ├─ interviews/          # interviews, panels, scorecards, calendar sync
│  │  ├─ offers/              # offers, joining, handholding milestones
│  │  ├─ notifications/       # templates, preferences, deliveries, in-app, websocket consumers
│  │  ├─ integrations/        # provider adapters, OAuth tokens, webhooks, logs
│  │  ├─ files/               # documents, versions, scanning, signed URLs
│  │  ├─ analytics/           # summary tables, dashboard endpoints, exports
│  │  ├─ audit/               # audit log, data-rights requests, retention
│  │  └─ migration_atlashiring/ # one-off import command
│  └─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ app/                 # providers, router, theme
│  │  ├─ api/                 # generated OpenAPI client + query hooks
│  │  ├─ components/          # shared UI (DataGrid wrappers, Kanban, Stepper, Uploader…)
│  │  ├─ features/            # auth, jobs, candidates, pipeline, interviews, offers, admin, dashboards
│  │  ├─ portals/             # careers (public), candidate, staff (admin/recruiter/client/consultant)
│  │  └─ realtime/            # WebSocket client, query invalidation
│  └─ e2e/
├─ infra/                     # docker-compose, Dockerfiles, nginx, IaC
├─ docs/                      # this spec, ADRs, API notes, runbooks
└─ .github/workflows/         # CI/CD
```

---

## 13. Data model (core entities)

Conventions: `BIGINT` auto-increment primary keys internally; a `public_id` UUID exposed in URLs/APIs; `created_at`, `updated_at`, `created_by`, `updated_by` on all business tables; soft delete (`deleted_at`) where records may be restored; JSON columns only for genuinely flexible structures (configs, parsed payloads, raw integration responses).

### 13.1 Identity & organisation
| Table | Key fields |
|---|---|
| `accounts_user` | email (unique), mobile_e164 (unique, nullable), password (nullable for OTP-only), first/last name, primary_role, client_id (client users), agency_id (consultants), is_active, email_verified_at, mobile_verified_at, mfa_enabled, last_login, timezone |
| `accounts_permission_set` / `accounts_role` | code, name, base_role, permissions (M2M), is_system |
| `accounts_user_permission_set` | user, permission_set |
| `accounts_otp_challenge` | target, channel, code_hash, purpose, attempts, expires_at |
| `clients_client` | name, legal name, code, industry, is_internal, status, address, GST/tax ID (optional), website, logo, default workflow template, settings (JSON: `client_can_publish`, approval chain) |
| `clients_client_contact` | client, user (nullable), name, designation, email, phone, is_primary |
| `clients_agency` | name, type (search / staffing / portal / referral / campus), status, commercial terms, SLA, account lead |

### 13.2 Jobs & workflow
| Table | Key fields |
|---|---|
| `workflow_template` | name, version, status (draft/active/archived), is_default, parent_template |
| `workflow_stage` | template, key, name, candidate_label, category, order, is_optional, sla_hours, flags (client_actionable, visible_to_*), on_enter_actions (JSON), next_step_text |
| `workflow_gate_item` | stage, gate_type (entry/exit), label, item_type, required |
| `jobs_job` | job_code, slug, client, entity, department, title, level, category, criticality, priority, status, headcount, filled_count, locations, work_mode, employment_type, exp_min/max, ctc_min/max (private), currency, description (rich text), accountabilities, competencies (JSON), qualifications, hiring_manager, target_sla_days, workflow_template_version, screening_profile, visibility, owner, published_at, closes_at, origin_notes |
| `jobs_job_skill` | job, skill, importance (must/good), min_years |
| `jobs_screening_question` | job, text, type, options, knockout_rule, weight |
| `jobs_job_assignment` | job, user or agency, role_on_job, assigned_by, start/end, target_submissions |
| `jobs_share_link` | shortcode (unique), job, created_by, channel, campaign, consultant, clicks, unique_clicks, applies |
| `jobs_job_approval` | job, approver, level, decision, comment, decided_at |

### 13.3 Candidates
| Table | Key fields |
|---|---|
| `candidates_candidate` | user (1:1, nullable until claimed), status (active/unclaimed/anonymised), headline, summary, current city, willing_to_relocate, total_exp_months, current_ctc, expected_ctc, notice_days, preferred_locations, work_mode_pref, linkedin_url, portfolio_url, photo, profile_completeness, completeness_breakdown (JSON), consents, created_via (apply/register/recruiter/consultant/import), provisional_identity (legacy import) |
| `candidates_experience` | candidate, title, company, start/end, is_current, description |
| `candidates_education` | candidate, degree, field, institute, year, grade |
| `candidates_skill` (+ `skills_skill` master with synonyms) | candidate, skill, years, level, source (parsed/self) |
| `candidates_resume` | candidate, document_version, parsed_json, parse_status, text (FULLTEXT index), is_primary |
| `candidates_duplicate_flag` | candidate_a, candidate_b, reason, score, status, resolved_by |
| `candidates_talent_alert` | candidate, criteria (JSON), channel, active |

### 13.4 Applications & pipeline
| Table | Key fields |
|---|---|
| `applications_application` | job, candidate, current_stage, status (active/hired/rejected/withdrawn), applied_at, declared_source, source_detail, link_channel, share_link, utm (JSON), referrer_domain, owner_recruiter, owner_consultant, screening_score, screening_band, stage_entered_at, sla_due_at, is_gate_overridden |
| `applications_stage_transition` | application, from_stage, to_stage, actor, at, reason, gate_evidence (JSON), override_reason |
| `applications_note` | application, author, visibility (atlas_private / internal_shared_with_client / consultant / candidate), body |
| `applications_candidate_ownership` | candidate, job, consultant/agency, valid_until, status, conflict_with |
| `applications_task` | application, assignee, title, due_at, status, type (follow-up, handholding milestone, feedback due) |
| `applications_answer` | application, question, answer, knockout_result |

### 13.5 Screening, assessments, interviews, offers
| Table | Key fields |
|---|---|
| `screening_profile` | name, knockouts (JSON), factor weights (JSON), ai_weight, auto_advance, auto_reject (bool), hold_hours |
| `screening_run` | application, trigger, rules_result (JSON), rules_score, ai_result (JSON), ai_score, composite, band, model_id, prompt_version, cost, status, error, created_at |
| `screening_override` | application, from_band, to_band, reason, actor |
| `assessments_job_config` | job, provider (criteria), provider_job_ref, tests (JSON), reference_ranges (JSON), approved_by, approved_at |
| `assessments_invite` | application, provider_ref, link, status, sent_at, expires_at |
| `assessments_result` | application, invite, event_id, started/completed, ccat_raw, ccat_percentile, excel_percentile, wpp_rating, talent_signal, score_ranges_met (JSON), invalid_flags (JSON), proctoring (JSON: overall score, monitoring, face throughout, face match, multiple people, phone, voices, recording loss, locked out), raw_payload, match_method, review (JSON gate checklist), reviewed_by |
| `interviews_interview` | application, type, round, start/end (UTC), timezone, mode, location, meet_link, organiser, calendar_event_id, status, observer |
| `interviews_panelist` | interview, user, role, feedback_due_at, attendance |
| `interviews_scorecard_template` | name, competencies (rows), from_job |
| `interviews_scorecard` | interview, panelist, ratings (rows with nullable values), weighted_score, recommendation, evidence, submitted_at, shared_with_client |
| `offers_offer` | application, version, designation, ctc_breakdown (JSON), joining_date, location, letter_document, status, approvals, released_at, responded_at, response_ip |
| `offers_joining` | application, expected_date, actual_date, status (joined/no-show/deferred) |
| `offers_handholding_milestone` | application, milestone (week1/training/day30/day90), due_at, completed_at, notes, owner |

### 13.6 Platform
| Table | Key fields |
|---|---|
| `files_document`, `files_document_version` | logical doc, kind (resume/jd/success_profile/offer/other), owner object (generic FK), version, name, mime, size, sha256, storage_key, scan_status, preview_text, archived |
| `notifications_template` | event, channel, locale, subject, body, provider_template_name (WhatsApp), active |
| `notifications_preference` | user, category, channel, enabled |
| `notifications_notification` | user, event, title, body, link, read_at |
| `notifications_delivery` | notification/event, channel, recipient, provider, provider_message_id, status, error, attempts |
| `core_outbox_event` | event_type, payload, status, attempts, created_at, processed_at |
| `integrations_credential` | provider, scope (global/user), user, encrypted_secret, expires_at |
| `integrations_log` | provider, direction, endpoint, status, latency, request_ref, error |
| `audit_log` | at, actor, actor_role, ip, action, object_type, object_id, changes (JSON diff), request_id — append-only (no update/delete permission at DB-user level) |
| `audit_data_request` | candidate, type (access/correct/erase), status, handled_by |
| `analytics_*` | daily funnel, source conversion, stage durations, recruiter/consultant metrics |

Key indexes: `application(job_id, current_stage_id, status)`, `application(candidate_id)`, `application(owner_consultant_id)`, `stage_transition(application_id, at)`, `job(client_id, status)`, `user(email)`, `user(mobile_e164)`, FULLTEXT on `resume.text` and `job.title/description`.

---

## 14. API design

- REST, JSON, versioned under `/api/v1/`; OpenAPI schema at `/api/v1/schema/`; cursor pagination; filtering via `django-filter`; consistent error envelope `{ "error": { "code", "message", "details" } }`.
- Idempotency keys on apply, offer release and integration callbacks.
- Webhooks under `/webhooks/<provider>/` with signature verification.
- WebSocket: `/ws/notifications/` (per user) and `/ws/jobs/<id>/pipeline/` (live Kanban for permitted staff).

| Area | Main endpoints |
|---|---|
| Auth | `POST auth/login`, `auth/otp/request`, `auth/otp/verify`, `auth/refresh`, `auth/logout`, `auth/password/reset`, `auth/mfa/*`, `GET me` |
| Admin | `users` CRUD, `roles`, `permission-sets`, `settings`, `audit`, `integrations/*`, `notification-templates` |
| Clients | `clients` CRUD, `clients/{id}/contacts`, `agencies` CRUD |
| Workflow | `workflow-templates` CRUD + `publish`, `stages`, `gate-items`, `jobs/{id}/migrate-template` |
| Jobs | `jobs` CRUD, `jobs/parse-jd` (upload → draft), `jobs/{id}/submit-for-approval`, `approve`, `publish`, `unpublish`, `close`, `assignments`, `share-links`, `screening-config`, `screening-questions` |
| Public (no auth) | `public/jobs` (search), `public/jobs/{code}`, `public/j/{shortcode}` (redirect), `public/apply/start`, `public/apply/verify`, `public/register`, `public/sources` |
| Candidates | `candidates` (staff search), `candidates/{id}`, `me/profile`, `me/profile/completeness`, `me/resumes`, `me/applications`, `me/applications/{id}/withdraw`, `candidates/duplicates`, `candidates/merge` |
| Applications | `applications` (scoped list), `{id}`, `{id}/move`, `{id}/notes`, `{id}/timeline`, `{id}/screening`, `{id}/screening/override`, `{id}/rescreen`, `bulk-move`, `bulk-message`, `submissions` (consultant submit), `ownership-conflicts` |
| Assessments | `jobs/{id}/assessment-config`, `applications/{id}/assessment/invite`, `assessment-results/import` (CSV), `assessment-results/{id}/review` |
| Interviews | `interviews` CRUD, `interviews/availability`, `{id}/reschedule`, `{id}/cancel`, `scorecard-templates`, `scorecards` |
| Offers | `offers` CRUD, `{id}/approve`, `{id}/release`, `me/offers/{id}/respond`, `joinings`, `handholding-milestones` |
| Notifications | `notifications`, `{id}/read`, `read-all`, `preferences` |
| Analytics | `dashboards/{role}`, `reports/funnel`, `reports/sources`, `reports/time-to-fill`, `reports/consultants`, `exports` |
| Data rights | `me/data-export`, `me/delete-request`, `admin/data-requests` |

---

## 15. Security, privacy and compliance

### 15.1 Application security
- OWASP ASVS Level 2 as the checklist; OWASP Top-10 tests in CI (dependency scanning, SAST) and a third-party penetration test before go-live.
- Staff MFA (TOTP) mandatory for Super Admin and Atlas Lead, recommended for all staff; account lockout and anomaly alerts.
- Session/token revocation on role change, deactivation or password reset (AtlasHiring behaviour kept).
- Rate limiting on auth, OTP, apply and public endpoints; bot challenge on public forms.
- Strict CORS, CSP, HSTS, secure cookies; signed short-lived file URLs; no PII in URLs or logs.
- Secrets in a secrets manager / environment, never in the repository; integration secrets encrypted at rest (Fernet / KMS).
- Database: least-privilege DB users (app user cannot `DELETE` from `audit_log`); encryption at rest; TLS in transit; daily backups + binlog point-in-time recovery.

### 15.2 Data scoping risks to test explicitly
Client A user cannot see client B; consultant cannot see other consultants' or direct candidates; candidate cannot see internal notes/scorecards; exports respect scope. Each has automated tests (§18).

### 15.3 India DPDP Act 2023 (and general privacy)
- Clear privacy notice and consent at apply/register (purpose: recruitment for NDT Atlas and its clients; sharing with the client for the applied job; optional talent pool; optional WhatsApp; AI-assisted screening with human review).
- Consent records stored with version and timestamp; withdrawable from the candidate settings page.
- Data-principal rights: access (self-service export), correction (profile editing), erasure (request → recruiter/admin review → anonymisation job), grievance contact.
- Retention policy (default proposal: inactive candidate data anonymised after 24 months; hired candidates per employment records policy) **[DECIDE]**, run by a scheduled job with reports.
- Hosting in an Indian region recommended (e.g. AWS Mumbai / Azure Central India) **[DECIDE]**; data shared with U.S. clients limited to what the application requires.
- Breach response runbook.

### 15.4 Audit
Every create/update/delete/move/export/download/login is in `audit_log` with before/after diff, actor, IP, request ID. Admin UI to search and export. Immutable at the database-permission level.

---

## 16. Non-functional requirements

| Area | Target (v1) |
|---|---|
| Scale | 100 staff users, 300 client/consultant users, 50,000 candidates and 150,000 applications in year 1; design headroom ×10 |
| Performance | API p95 < 400 ms for lists/detail; public job page TTFB < 500 ms (cached); apply submit < 2 s; parsing + screening < 60 s per resume (async) |
| Real-time | Stage change visible to the candidate in < 5 s |
| Availability | 99.5% monthly (business hours IST + U.S. overlap critical) |
| Backup / DR | RPO ≤ 1 h (binlog PITR), RTO ≤ 4 h; quarterly restore drill |
| Browser support | Last two versions of Chrome, Edge, Safari, Firefox; Android Chrome, iOS Safari |
| Accessibility | WCAG 2.2 AA |
| Observability | Centralised logs, error tracking, uptime checks, queue depth and integration-failure alerts |

---

## 17. AtlasHiring data migration (M16)

The reference package contains real personal data (67 application/source records, 45 assessment attempts, 48 JD files and other candidate documents). It must only be imported into a secured staging/production environment, never committed to the repository.

| AtlasHiring source | TIS target | Notes |
|---|---|---|
| 20 inventory positions + 4 critical requisitions (kept separate, e.g. Dispatch L4 vs L5 never merged) | `jobs_job` (status mapped: Active Open → Published; historical/filled → Filled/Closed), criticality/priority flags | Critical tracker "next action" → task |
| 6 partners (StratBoard Search, WhiteForce, Naukri Direct, Referrals, Direct/LinkedIn, Campus) | `clients_agency` + source master | Normalise "White Force"/"WhiteForce" and "StartBoard"/"StratBoard Search" only after HR confirms they are the same agency **[DECIDE]** |
| 67 candidate/application rows | `candidates_candidate` (`provisional_identity = true`, `created_via = import`) + `applications_application` | No automatic identity merging; `possibleDuplicates` → duplicate flags |
| Stage keys (`screen`, `verbal`, `shortlist`, `assessment`, `simulation`, `interview`, `submission`, `client`, `decision`, `offer`, `joined`, `handholding`, `closed`, `unconfirmed`) | Atlas Standard v1 stages (1:1 mapping; `unconfirmed` → `screening` with a "stage not confirmed" flag) | Stage history imported as transitions; unknown dates stay null |
| 45 Criteria attempts | `assessments_result` (raw payload kept; matched by normalised email then name; ambiguous matches left unlinked for review) | Review flags imported as-is; no pass/fail inferred |
| 48 JD files + 1 Success Profile (+ metadata catalogue) | `files_document` versions linked to jobs where AtlasHiring linked them; others in an "unlinked JDs" review queue | SHA-256 verified on import |
| Users | Not migrated (password hashes excluded by design); recreated and invited | |
| Audit log | `audit_log` with `source = atlashiring` | |
| Validation rules, issues list | Imported as a reconciliation checklist for HR | |

Implemented as `python manage.py import_atlashiring --backup <file> --dry-run`, producing a reconciliation report (counts in/out, unmatched, flagged) before a confirmed run.

---

## 18. Testing and quality strategy

| Level | Tooling | Focus |
|---|---|---|
| Unit | pytest, Vitest | Workflow engine (gates, transitions), screening scoring, completeness calculation, permission scoping, dedupe |
| API / integration | pytest + DRF test client, factory_boy | Every endpoint × every role × scope (generated permission test matrix) |
| Contract | OpenAPI schema diff in CI; mocked provider adapters | Integration adapters against recorded fixtures; webhook signature checks |
| End-to-end | Playwright | Golden paths: post job by JD upload → share link → apply with OTP → screening → pipeline to offer → candidate sees updates live; client review flow; consultant submission + ownership conflict |
| AI evaluation | Labelled set (≈100 resumes × jobs, recruiter decisions) | Band agreement with recruiters, extraction field accuracy, bias checks (score stability when redacted attributes vary); rerun on every prompt/model change |
| Performance | Locust / k6 | Public job pages, apply burst after a social post, dashboard queries at target data volume |
| Security | Bandit, pip-audit, npm audit, OWASP ZAP baseline, external pentest | |
| Accessibility | axe in Playwright, manual screen-reader pass | |
| UAT | Scripted scenarios per role with NDT Atlas HR, a pilot client and a pilot consultant | |

Definition of Done per story: code reviewed, tests passing with coverage ≥ 80% on backend domain modules, OpenAPI updated, permissions tested, audit events emitted, docs/ADR updated, deployed to staging, PO accepted.

---

## 19. Environments, DevOps and deployment

- **Local:** Docker Compose — MySQL, Redis, backend (runserver/uvicorn), Celery worker + beat, frontend (Vite), Mailpit (email capture), MinIO (S3), ClamAV.
- **Environments:** dev (auto-deploy from `main`), staging (release candidates, anonymised data), production.
- **CI (GitHub Actions):** ruff + mypy + pytest; eslint + tsc + Vitest; OpenAPI drift check; migrations check; dependency audit; Docker image build; Playwright on staging.
- **CD:** tagged releases → staging → manual approval → production; zero-downtime migrations (expand/contract).
- **Hosting (recommended, [DECIDE]):** containers on a managed platform in an Indian region; managed MySQL with a read replica and PITR; managed Redis; S3-compatible object storage; CDN + WAF in front; separate worker pool for Celery and an ASGI pool for WebSockets.
- **Domains:** `careers.<company-domain>` (public + candidate) and `tis.<company-domain>` (staff), or a single domain with path routing **[DECIDE]**.

---

## 20. Development plan

### 20.1 Team (recommended)
| Role | FTE |
|---|---|
| Tech lead / architect (full-stack, Django) | 1 |
| Backend developers (Django/DRF/Celery) | 2 |
| Frontend developers (React/MUI) | 2 |
| QA engineer (automation + manual) | 1 |
| UI/UX designer | 0.5 |
| DevOps engineer | 0.5 |
| Product owner (NDT Atlas HR/recruitment lead) | 0.5 — decisions, backlog, UAT |

Two-week sprints. With this team the plan below is ~34 weeks (≈8 months) to production, with a usable internal pilot at ~week 20. A smaller team stretches the timeline roughly proportionally; scope can also be trimmed by moving phases 5b/6b items to v1.1.

### 20.2 Phases and sprints

| Phase | Sprints (weeks) | Deliverables | Exit / acceptance criteria |
|---|---|---|---|
| **0. Mobilise** | S0 (1–2) | Sign-off of this spec and §22 decisions; UX wireframes for key flows (apply, pipeline, candidate tracker, dashboards); design system in MUI theme; monorepo, CI, Docker Compose, dev/staging environments; ADRs. **Start long-lead items:** WhatsApp business verification + templates, email domain SPF/DKIM/DMARC, Google Cloud project + OAuth consent screen, Criteria API access, AI provider data-processing approval | Wireframes approved; "hello world" deployed to staging through CI; long-lead requests submitted |
| **1. Foundation** | S1–S2 (3–6) | Custom user model, login/logout, OTP service, staff MFA, password reset; roles, permission sets, matrix editor; scoped querysets; user CRUD + invites; client & agency CRUD; audit log; file service with scanning; app shell (navigation per role, theme, dark mode, command palette skeleton) | Super Admin can create every user type and clients; permission test matrix green; audit visible |
| **2. Jobs & careers site** | S3–S4 (7–10) | Workflow template engine + "Atlas Standard v1" seed + template editor (basic); job form (multi-step, draft, approval, publish); JD upload → parse → prefilled form; assignments; share links + shortcode redirects + QR; public careers site with SSR meta, JSON-LD, sitemap | Recruiter posts a job by form and by JD upload, assigns it, shares a tracked link that previews correctly on LinkedIn/WhatsApp |
| **3. Candidate & apply** | S5–S6 (11–14) | Apply flow with auto sign-up + OTP; standalone registration; source dropdown + attribution capture; resume upload + parsing + profile prefill; candidate profile editor; completeness meter + nudges; duplicate detection; candidate dashboard with application tracker; email notifications (provider live) | A candidate goes from a shared link to a submitted application in < 2 minutes on a phone; completeness updates live; duplicates flagged |
| **4. Pipeline & screening** | S7–S9 (15–20) | Kanban + list views, stage moves with gates/overrides, notes (visibility levels), tasks; hybrid screening (L1, L2, L3, composite, review queue, overrides, re-screen, batch); AI evaluation set and report; consultant submissions + ownership conflicts; client portal (review, feedback, decisions); WebSockets + in-app notification centre; outbox event bus | **Internal pilot go-live** on 2–3 real jobs: screening produces explainable bands; candidates see stage updates in real time; client and consultant flows work with correct scoping |
| **5. Integrations & late stages** | S10–S12 (21–26) | (a) WhatsApp adapter + templates + opt-in/out + receipts; Google Calendar OAuth, availability, Meet events, sync; interview scheduling, panels, reminders; row-based scorecards + feedback SLA. (b) Criteria config, CSV import first then API invites/results, assessment review gate; offers (approval, release, e-acceptance), joining, 90-day handholding milestones | Full AtlasHiring process runs end to end on a pilot job including Criteria review gate, client interview with silent observer and offer → joined → handholding |
| **6. Dashboards, analytics & migration** | S13–S14 (27–30) | Role dashboards (6) with drill-downs; reports & exports; summary tables; scheduled report emails; AtlasHiring import command + dry-run reconciliation + HR review; notification template admin UI | Dashboards match hand-checked numbers on pilot data; AtlasHiring data imported to staging with a signed-off reconciliation report |
| **7. Hardening & launch** | S15–S16 (31–34) | Performance/load tests, security fixes, external penetration test, accessibility audit, DPDP checklist (consents, data-rights flows, retention job), backup/restore drill, runbooks, user guides & training videos per role, UAT with HR, a pilot client and a pilot consultant; production cut-over (migration of AtlasHiring data), hypercare (2 weeks) | UAT sign-off; no open critical/high security findings; restore drill passed; go-live |

### 20.3 Release milestones
| Milestone | Week | Content |
|---|---|---|
| M1 — Staff foundation | 6 | Users, roles, clients, audit |
| M2 — Public jobs live (internal test) | 10 | Job posting + share links + careers site |
| M3 — Apply & candidate portal | 14 | Apply/auto sign-up, profile, completeness |
| **M4 — Internal pilot** | **20** | Pipeline, hybrid screening, real-time updates, client & consultant portals, email |
| M5 — Full process | 26 | WhatsApp, Calendar, Criteria, offers, handholding |
| M6 — Analytics & migration | 30 | Dashboards, AtlasHiring data |
| **M7 — Production go-live** | **34** | Hardened, trained, migrated |

### 20.4 Initial backlog (Sprint 1 ready epics)
1. EPIC-AUTH: custom user model, email/password + OTP login, JWT cookies, refresh, logout, reset, MFA for staff.
2. EPIC-RBAC: roles, permission sets, matrix API + UI, scoped queryset framework, permission test generator.
3. EPIC-CLIENT: client & contact CRUD, agency CRUD, client user invites.
4. EPIC-AUDIT: audit middleware/signals, admin audit viewer.
5. EPIC-FILES: upload service, scanning, storage, signed URLs, versions.
6. EPIC-SHELL: React app shell, MUI theme (light/dark), role-based navigation, auth screens, generated API client.

---

## 21. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| WhatsApp business verification / template approval delays | WhatsApp late at launch | Start in Sprint 0; email covers every notification; adapter allows switching BSP |
| Criteria API access not available or limited | Manual result handling | CSV import built first (works on day one); API added when access confirmed |
| AI screening inaccurate or perceived as biased | Wrong rejections, candidate complaints | Advisory only; human review; PII redaction; evaluation set before go-live; no auto-reject except opt-in hard knock-outs with hold period; full explanations |
| Data leakage across clients/consultants | Contractual and legal exposure | Server-side scoping layer, generated permission tests, pentest focused on IDOR |
| Workflow configurability becomes too complex | Delays, confusing UI | Ship one solid default template; editor limited to documented properties; template versioning |
| Legacy AtlasHiring data quality (missing emails, ambiguous identities, inferred thresholds) | Dirty data in new system | Provisional identities, dry-run reconciliation, HR sign-off, no auto-merge |
| Email deliverability (OTPs in spam) | Candidates cannot sign up | SPF/DKIM/DMARC, reputable provider, WhatsApp/SMS OTP fallback |
| Social traffic spikes after a viral post | Slow apply page | CDN-cached public pages, async parsing, load tests on apply |
| Scope creep (job-board APIs, HRMS, payouts) | Timeline slip | Out-of-scope list (§1.1); change requests go to v1.1 backlog |
| DPDP compliance gaps | Regulatory risk | Consent, rights and retention features in plan; legal review of notice text before launch |

---

## 22. Decisions needed (owner + needed-by sprint)

| # | Decision | Recommendation | Needed by |
|---|---|---|---|
| D1 | Can client users publish jobs directly, or only raise requisitions for Atlas to publish? | Raise only; per-client flag `client_can_publish` (off) | S3 |
| D2 | Can client users invite colleagues from their own company? | Yes, limited to their client, Atlas Lead notified | S2 |
| D3 | Do client users approve offers? | Optional per client (flag) | S11 |
| D4 | Consultant visibility of candidate contact details for candidates they did not source | Hidden | S7 |
| D5 | Auto-reject policy | Off by default; opt-in per job for hard knock-outs, 24 h hold | S7 |
| D6 | AI provider data-processing approval (redacted resume text to Claude API) and model choice | Approve with DPA; default `claude-opus-5-5`, configurable | S0 |
| D7 | Candidate-visible feedback depth | Stage + recruiter-written message only | S7 |
| D8 | Email provider | Amazon SES or SendGrid via anymail | S0 |
| D9 | WhatsApp: Meta Cloud API direct vs BSP | BSP if local support/billing in INR matters; otherwise Cloud API | S0 |
| D10 | Google Workspace in use at NDT Atlas? (service account vs per-user OAuth) | Per-user OAuth works either way | S0 |
| D11 | Hosting provider and region | Indian region of an established cloud | S0 |
| D12 | Data retention period for inactive candidates | 24 months then anonymise | S14 |
| D13 | Are "White Force"/"WhiteForce" and "StartBoard"/"StratBoard Search" the same agencies? | HR to confirm before import | S13 |
| D14 | Stage order: Offer → Joined → 90-day handholding (vs AtlasHiring numbering) | Yes | S0 |
| D15 | Approval of SLA targets (feedback hours, offer 24 h, hire 5–7 days) and Criteria reference ranges per role | Leave unset until baselined from pilot data | S10 |
| D16 | Domains for careers site and staff portal | `careers.` + `tis.` subdomains | S2 |
| D17 | Consultant ownership window | 90 days per job | S8 |

---

## Appendix A — Requirement traceability

| # | Original requirement | Where covered |
|---|---|---|
| 1 | User types: Super Admin, Atlas recruiter, client recruiter/POC, external recruiter/consultant, candidate | §3.1, §3.2 |
| 2 | Client management CRUD | §3.2, §13.1, §14 (Clients), Phase 1 |
| 3 | Atlas recruiters post jobs; assign to consultants or Atlas recruiters | §7.1–7.4, §13.2 |
| 4 | Unique shareable link per job → portal → details → apply | §7.5 |
| 5 | Applying auto-signs the candidate up with basic details | §8.1 (plus standalone registration §8.2) |
| 6 | Profile completeness percentage | §8.3 |
| 7 | Super Admin full rights; CRUD all users; assign rights | §3.1–3.3, §15.4 |
| 8 | Ask job source with dropdown (Facebook, LinkedIn, Naukri, …) | §7.6 |
| 9 | Automated resume screening on predefined parameters | §6 (hybrid) |
| 10 | Every user has a dashboard | §11 |
| 11 | Recruiter updates screening/interview feedback; candidate sees real-time updates | §5, §8.4, §8.6, §9 |
| 12 | Post jobs by form or by uploading a Word/PDF JD | §7.2 |
| 13 | Use AtlasHiring staging and recruitment parameters | §2, §5.2, §10.4, §17 |
| — | Decisions: single org, both registration modes, full client access, hybrid screening, Email/WhatsApp/Calendar/Criteria, configurable stages | §1, §5, §6, §10 |
