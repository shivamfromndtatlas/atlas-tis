# NDT Atlas — Talent Intelligence System (TIS)

In-house, end-to-end recruitment platform for NDT Atlas, its clients, external consultants and candidates.
The full architecture and development plan is in
[docs/TIS_Architecture_and_Development_Spec.md](docs/TIS_Architecture_and_Development_Spec.md).

| Part | Stack |
|---|---|
| `backend/` | Python 3.12+, Django 5.2, Django REST Framework, MySQL 8, Celery + Redis |
| `frontend/` | React 18, TypeScript, Vite, Material UI 6, MUI X Data Grid, TanStack Query |
| `infra/` | Docker Compose for local development, backend Dockerfile |
| `.github/workflows/` | CI: lint, migrations check, OpenAPI drift, tests (MySQL), typecheck, build |

## Sprint 1 scope (delivered)

- **Auth (EPIC-AUTH):** email + password, email one-time code, TOTP two-step verification (mandatory for
  Super Admin and Atlas Lead), invites, password reset and change. JWT in httpOnly cookies with CSRF
  protection, refresh rotation + blacklist, and instant revocation of every session on role change,
  deactivation or password reset.
- **RBAC (EPIC-RBAC):** capability registry, editable role × capability matrix, add-on permission sets
  (Atlas Lead), custom sets, server-side row scoping (client users see only their company, consultants
  only their agency). A generated test matrix checks every role against every endpoint.
- **Clients & agencies (EPIC-CLIENT):** CRUD with soft archive, client contacts, per-client flags
  (`client_can_publish`, …), NDT Atlas modelled as an internal client.
- **Audit (EPIC-AUDIT):** append-only log of every create/update/delete with field diffs, sign-ins,
  failed sign-ins and downloads; secrets are never logged.
- **Files (EPIC-FILES):** versioned documents, extension + magic-byte checks, size limits, SHA-256,
  ClamAV hook, short-lived signed download links with audit.
- **App shell (EPIC-SHELL):** role-aware navigation, light/dark theme, Ctrl+K command palette, dashboard,
  users, roles matrix, clients, agencies, audit log and account pages.

## Run locally without Docker (SQLite)

Prerequisites: Python 3.12+ and Node 22+.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements\dev.txt
copy .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL=sqlite:///db.sqlite3` (no MySQL needed), then:

```powershell
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo --password "Choose-A-Long-Passw0rd"
.venv\Scripts\python manage.py runserver
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in as any demo user (`admin@`, `lead@`, `recruiter@`, `client@`,
`consultant@`, `candidate@` `tis.local`) with the password you chose. Emails (invites, codes, resets)
print in the Django terminal. `admin@` and `lead@` must enrol an authenticator app on first sign-in.

API docs: http://localhost:8000/api/v1/docs/

## Run with Docker (MySQL, Redis, Mailpit)

```powershell
docker compose -f infra/docker-compose.yml up --build
```

Then seed demo data with `docker compose -f infra/docker-compose.yml exec backend python manage.py
seed_demo --password "Choose-A-Long-Passw0rd"`. Emails appear at http://localhost:8025.

## First real Super Admin (staging / production)

There are no default passwords. Create the first admin, who receives an invite email:

```powershell
python manage.py bootstrap_superadmin --email someone@example.com --first-name Pat --last-name Doe
```

## Checks

```powershell
cd backend; .venv\Scripts\ruff check .; .venv\Scripts\python -m pytest
cd frontend; npm run typecheck; npm run lint; npm test; npm run build
```

After changing any API serializer or view, regenerate the schema and the TypeScript types:

```powershell
cd backend; .venv\Scripts\python manage.py spectacular --file openapi.yaml
cd frontend; npm run gen:api
```

## Conventions

- Every new endpoint declares a `capability_map` (actions not listed are denied) and scopes its queryset
  with the model's `for_user()`; add the endpoint to `backend/tests/test_permissions.py`.
- Errors use one envelope: `{"error": {"code", "message", "details"}}`.
- Raising an API error rolls back the request transaction. When a failure must leave a trace (failed
  sign-in audit, OTP attempt counter), return `error_response(...)` instead of raising.
- Models exposed in URLs use `public_id` (UUID); internal integer keys never leave the server.
- Legacy AtlasHiring data contains personal data: never commit it (see `.gitignore`).
