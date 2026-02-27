# AspectNova — Status Checklist (Pre-Level-Up Gate)

This checklist defines the minimum "green gates" required before moving to a higher reliability level (worker/queue, multi-run concurrency, etc.).

## 0) Scope & Safety Rules (Non-negotiable)
- [ ] Never run destructive execution on the project root. Use a sandbox path or an explicit allowlist scope.
- [ ] Never delete `.aspectnova\contracts\*` or `.aspectnova\archive\*` without an explicit retention policy.
- [ ] Every destructive execution must require a confirm secret (approval + confirm).
- [ ] Artifacts must be reproducible from inputs (scan + rules) and traceable.

---

## 1) API Health & Control Plane
- [ ] `GET /health` returns `{ "status": "ok" }`
- [ ] `POST /api/v1/workspaces/ws_api/runs` creates a run and returns a valid `run_id`
- [ ] Approve endpoint validates secret correctly:
  - invalid secret => 401/403
  - valid secret => approved
- [ ] Execute endpoint validates inputs (422 on missing fields) and runs pipeline
- [ ] Job status transitions work:
  - `queued -> approved -> running -> completed` OR `failed`
- [ ] Job logs always exist and are readable on failure:
  - `.aspectnova\jobs\ws_api\<RUN_ID>\logs\stdout.log`
  - `.aspectnova\jobs\ws_api\<RUN_ID>\logs\stderr.log`

---

## 2) Contracts & Artifacts (Must Exist on Completed Runs)
For a completed run, these must exist:
- [ ] `.aspectnova\contracts\ws_api\<RUN_ID>\cleanup_targets.json`
- [ ] `.aspectnova\contracts\ws_api\<RUN_ID>\execution_report.json`
- [ ] `.aspectnova\archive\ws_api\<RUN_ID>\manifest.json`
- [ ] `.aspectnova\archive\ws_api\<RUN_ID>\payload.zip`

And these must be internally consistent:
- [ ] `execution_report.archive.zip_sha256` == `Get-FileHash payload.zip -Algorithm SHA256`
- [ ] `manifest.payload_zip_sha256` == same SHA256
- [ ] `execution_report.summary.errors` == 0 (for the happy-path test)
- [ ] `execution_report.summary.targets_total` matches `cleanup_targets.summary.targets_total`

---

## 3) Safety Behavior (Proof)
- [ ] Running with safe_mode=true does not modify files.
- [ ] Running with execute=true requires a confirm secret.
- [ ] Allowed scopes are enforced; out-of-scope files are NOOP.

---

## 4) Reproducibility & Repeatability
- [ ] `scripts\run_cleanup_test.ps1` (or equivalent test runner) can be executed end-to-end and produces a "completed" run.
- [ ] Re-running the same sandbox produces stable outcomes (NOOP where expected).

---

## 5) Evidence Pack (What to Attach in Reviews)
For any "level up" decision, capture:
- Run ID
- cleanup_targets.json
- execution_report.json
- manifest.json
- payload.zip + SHA256
- stderr/stdout logs
- trace_contract.json (if present)
