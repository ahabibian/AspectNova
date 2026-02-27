# RELEASE PROCESS — DV Toolchain

This project follows controlled release discipline.

---

## Pre-Release Checklist

1. Run gate:

    .\dv.ps1 gate

2. Run renormalization check:

    git add --renormalize .
    git status

3. Ensure:
   - No dev artifacts
   - No dirty working tree
   - No experimental patches

4. Verify:
   - Contracts match implementation
   - No debug prints left
   - No temporary logging

---

## Version Bump

Update version in:
- VERSION file (if exists)
- config/version constant
- changelog

Follow semantic versioning:

MAJOR — breaking contract changes  
MINOR — new stage / new capability  
PATCH — bugfix only  

---

## Tag Release

Example:

    git tag v0.2.0
    git push origin v0.2.0

---

## Release Must Pass Gate

Never tag a release without:
    .\dv.ps1 gate == OK

---

## Post-Release Rule

After release:
- No direct commits to production branch
- All changes via review