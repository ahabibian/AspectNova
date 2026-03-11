# Repo Scope - AspectNova Legacy Technical Repo

## Classification
Legacy mixed technical repository.

## Main purpose
This repository remains useful as a reference and extraction source for:
- historical Data Verdict work
- technical ADRs
- engine-related experiments
- contract evolution
- existing run artifacts

## Explicit non-goal
This repository is not the clean target for the new DW Platform v1 implementation.

## Relationship to other roots
- Legacy technical repo:
  C:\dev\AspectNova

- Active new platform repo:
  C:\dev\dw-platform

- Clean curated docs root:
  C:\dev\AspectNovaDocs

## Usage rules
1. Keep this repo readable, but do not over-refactor it unnecessarily
2. Prefer extracting useful logic into dw-platform later instead of mutating this repo aggressively
3. Keep curated planning and product docs out of this repo
4. Use this repo as canonical source for old technical ADRs unless explicitly replaced

## Cleanup policy
Allowed:
- README improvements
- scope clarification
- maintenance script grouping
- minor structural readability fixes

Not allowed without explicit decision:
- repo rename
- major folder migrations
- destructive cleanup of historical code
- large-scale restructuring of core code folders
