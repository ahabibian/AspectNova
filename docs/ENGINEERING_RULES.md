# ENGINEERING RULES — DV / AspectNova Agent

Status: ENFORCED  
Scope: Entire repository  
Owner: Maintainer

---

## 1. Quality Gate Is Mandatory

Before **every commit**:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\dv.ps1 gate

If gate fails:
- You DO NOT commit
- You DO NOT push
- You FIX the issue first

Gate includes:
- STRIP_BOM
- DEVGUARD
- compileall checks
- stage integrity verification

No exceptions.

---

## 2. Deterministic Writes Only

All file writes MUST:
- Use UTF-8 without BOM
- Be deterministic
- Avoid random ordering
- Avoid environment-dependent formatting

Forbidden:
- Set-Content
- Out-File
- Add-Content
- >>
- Any non-UTF8 write without explicit encoding

Use approved toolkit only.

DEVGUARD enforces this.

---

## 3. Stage Contract Discipline

Each stage:
- Reads only its defined input contract
- Writes only its defined output contract
- Does NOT access random files
- Does NOT depend on implicit filesystem state

If a stage needs new input:
- Update contract version
- Document in ADR
- Bump minor version

No silent coupling allowed.

---

## 4. No Dev Artifacts in Repository

Never commit:
- snapshots
- baselines
- local archives
- experimental patch files
- temporary debugging scripts

If it’s not runtime-critical, it does not belong in repo.

---

## 5. Reproducibility

Pipeline output must be reproducible:
- Same input → same output hash
- Stable sorting everywhere
- Stable ID generation
- No time-based randomness unless explicitly declared

---

## 6. Line Ending Policy

Controlled by `.gitattributes`.

Never manually fight LF/CRLF.
Never override Git normalization.

---

## 7. Refactoring Rules

Refactor only if:
- Gate passes before change
- Gate passes after change
- Behavior is proven unchanged

No speculative rewrites.

---

## 8. Versioning Discipline

Any change affecting:
- Contract
- Output schema
- Stage behavior

Requires:
- Version bump
- ADR entry

---

Violations of these rules = regression risk.

This project is not a prototype.
This is a system.