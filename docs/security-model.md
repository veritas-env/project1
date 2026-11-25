# Security model

ProjectFlow's security controls. Each row names the code that implements the control
and the test suite that proves it. Business rules and threats are in section 3.

## 1. Trust boundaries

```
Browser ──HTTPS──▶ VPS TLS gateway ──▶ app Nginx ──▶ frontend (Next.js)
                                                └──▶ backend (FastAPI) ──▶ Postgres, Redis
```

- Only the app's Nginx publishes a port, on 127.0.0.1, for the gateway.
- Frontend, backend, Postgres and Redis are on internal Docker networks with no internet route.
- The backend trusts `X-Forwarded-For` only from the app's own Nginx (fixed address).
- The running app connects to Postgres as `app_rw` (data only, no DDL). Migrations run
  as `app_owner` in a one-shot container.

## 2. Controls by OWASP Top 10:2025 category

| Cat | Control | Where | Proven by |
|---|---|---|---|
| A01 | Every route requires a session except sign-in; tenant routes require membership via `org_access(min_role)`; resources loaded by `(org_id, id)`; non-members get 404; CSRF token on all writes; JSON-only bodies; uploads stored by UUID; no redirects | `api/deps.py`, every router | `test_a01_access_control.py` (routes enumerated from OpenAPI) |
| A02 | Production refuses weak secrets and default DB credentials; API docs off in production; no CORS; security headers in Nginx; no version banners; generic JSON errors; hardened containers (read-only, no capabilities, no egress) | `core/config.py`, `main.py`, `deployment/` | `test_a02_configuration.py`, `security/acceptance/check_deployment.py` |
| A03 | Python deps hash-locked; npm lockfile with sha512 integrity and exact versions; base images and actions pinned by digest/SHA; pip-audit, npm audit, Trivy gate CI; SBOM per build | `backend/requirements*.lock`, `frontend/package-lock.json`, `deployment/`, `.github/workflows/ci.yml` | `test_a03_supply_chain.py`, CI |
| A04 | argon2id passwords; 256-bit tokens from `secrets`; session tokens stored only as SHA-256 digests; HMAC-SHA256 signed values with purpose and expiry; TLS at the gateway | `core/security.py`, `core/sessions.py` | `test_a04_cryptography.py` |
| A05 | Bound parameters only; sort/order allow-listed; LIKE wildcards escaped; React escaping, no raw HTML; validation errors don't echo input; downloads are attachments with `nosniff` | `api/tasks.py`, `api/documents.py`, `core/errors.py`, frontend | `test_a05_injection.py` |
| A06 | Limits on page size, field length, upload size and type; last owner can't be removed; members edit only tasks they created or are assigned | routers, `schemas/` | `test_a06_business_rules.py` |
| A07 | Server-side sessions; new token every sign-in; logout and password change revoke server-side; idle 30 min / absolute 8 h; per-account lockout; per-IP rate limit (app and Nginx); generic errors; constant-time unknown-user path; password policy | `api/auth.py`, `core/sessions.py` | `test_a07_authentication.py` |
| A08 | Server computes file hashes; request models reject unknown fields (no mass assignment); no deserialisation of user data | `api/documents.py`, `schemas/` | `test_a08_integrity.py` |
| A09 | Security events for sign-in, sign-out, denials, CSRF, lockout, role changes, password changes, rejected uploads; written in their own transaction; append-only (trigger + grants); immediate and threshold alert rules; admin alert view | `services/audit.py`, migration 0001 | `test_a09_logging_alerting.py` |
| A10 | One transaction per request with rollback on any error; generic 500 with request ID; fail closed when Redis is down; failed uploads leave nothing behind | `core/db.py`, `core/errors.py`, `api/documents.py` | `test_a10_exceptions.py` |

## 3. ProjectFlow threat model

| Asset | Threat (STRIDE) | Abuse case | Control | Test |
|---|---|---|---|---|
| Workspace data | Information disclosure | A user reads another company's projects, tasks or documents | All workspace data is reachable only by workspace members; non-members get 404 | `test_a01` (route enumeration) |
| Tasks | Tampering | A member edits or deletes colleagues' tasks | Members edit only tasks they created or are assigned; only managers delete | `test_a01::test_role_matrix` |
| Membership | Elevation of privilege | A member promotes themself or a manager hands out manager roles | Only owners change roles or invite managers; role elevation raises an alert | `test_a01`, `test_a09` |
| Workspace | Denial of service | The last owner is demoted or removed, leaving the workspace unmanaged | At least one owner is always kept | `test_a06` |
| Invitations | Spoofing | An invitation link is guessed, reused, forwarded or used after revocation | 256-bit single-use token, stored as a digest, bound to the invited email, 7-day expiry, re-invite revokes the old link, public endpoints rate-limited | `test_a06`, `test_a01::test_invitation_bound_to_invited_email` |
| Invitations | Spoofing | Registering through an invitation takes over an existing account | Registration refused when the email already has an account | `test_a06` |
| Assignments | Tampering | A task is assigned to someone outside the workspace, or to another project's milestone | Assignees and project leads must be members; milestones must belong to the task's project | `test_a01::test_assignments_cannot_reference_other_workspaces`, `test_a06` |
| Projects | Tampering | Work continues on an archived project | Archived projects accept no new tasks | `test_a06` |
| Documents | Tampering / XSS | Uploaded HTML or scripts run in users' browsers | Content-sniffed allow-list, stored by UUID, served as attachments with `nosniff` and a sandbox CSP | `test_a05`, `test_a06` |
