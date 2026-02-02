@echo off
setlocal EnableExtensions

REM ------------------------------------------------------------
REM AspectNova - EII Engine Pipeline (enterprise-aligned)
REM ------------------------------------------------------------

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "OUT=%ROOT%\out"
if not exist "%OUT%" mkdir "%OUT%"

REM ----------------------------
REM Inputs / Outputs
REM ----------------------------
set "REQUEST=%ROOT%\scan_request.test.json"

set "OUT_SCANRES=%OUT%\scan_result.debug.json"
set "OUT_EII=%OUT%\eii_result.json"
set "OUT_SCANPAYLOAD=%OUT%\scan_payload.json"
set "OUT_PROPOSAL=%OUT%\cleanup_proposal.json"
set "OUT_PLAN=%OUT%\command_plan.json"
set "OUT_EXEC=%OUT%\execution_report.dryrun.json"

REM ----------------------------
REM Tools
REM ----------------------------
set "TOOL_VALIDATE=%ROOT%\contracts\tools\validate_schema.py"
set "TOOL_POLICY=%ROOT%\contracts\tools\enforce_policy.py"
set "TOOL_BUILD_SCANPAYLOAD=%ROOT%\contracts\tools\build_scan_payload.py"
set "TOOL_ADAPTER=%ROOT%\contracts\tools\cleanup_adapter.py"
set "TOOL_BUILD_PLAN=%ROOT%\contracts\tools\build_command_plan.py"
set "TOOL_DRYRUN=%ROOT%\contracts\tools\execute_plan_dryrun.py"

REM ----------------------------
REM Schemas
REM ----------------------------
set "SCHEMA_REQUEST=%ROOT%\contracts\schemas\aspectnova.scan_request.v1.json"
set "SCHEMA_SCANPAYLOAD=%ROOT%\contracts\schemas\aspectnova.scan_payload.v1.json"
set "SCHEMA_EXEC_REPORT=%ROOT%\contracts\schemas\aspectnova.execution_report.v1.json"

REM ----------------------------
REM Engine
REM ----------------------------
set "RUN_EII=%ROOT%\run_eii.py"

REM ----------------------------
REM Preflight
REM ----------------------------
if not exist "%REQUEST%" (
  echo [PIPELINE] ERROR: scan request not found: "%REQUEST%"
  goto :fail
)

if not exist "%RUN_EII%" (
  echo [PIPELINE] ERROR: run_eii.py not found: "%RUN_EII%"
  goto :fail
)

REM ------------------------------------------------------------
REM 1/9 Validate scan_request schema
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 1/9 Validating scan_request schema...
if exist "%TOOL_VALIDATE%" (
  if exist "%SCHEMA_REQUEST%" (
    python "%TOOL_VALIDATE%" "%REQUEST%" "%SCHEMA_REQUEST%"
    if errorlevel 1 goto :fail
  ) else (
    echo [PIPELINE] WARN: request schema not found, skipping: "%SCHEMA_REQUEST%"
  )
) else (
  echo [PIPELINE] WARN: validate_schema tool not found, skipping.
)

REM ------------------------------------------------------------
REM 2/9 Run EII engine (uses scan_request)
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 2/9 Running EII engine...
python "%RUN_EII%" --scan "%REQUEST%" --out "%OUT_EII%"
if errorlevel 1 goto :fail
echo [PIPELINE] OK -> wrote: "%OUT_EII%"

if not exist "%OUT_SCANRES%" (
  echo [PIPELINE] ERROR: expected scan_result.debug.json not found: "%OUT_SCANRES%"
  goto :fail
)

REM ------------------------------------------------------------
REM 3/9 Build scan_payload (enterprise artifact)
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 3/9 Building scan_payload...
if not exist "%TOOL_BUILD_SCANPAYLOAD%" (
  echo [PIPELINE] ERROR: build_scan_payload tool not found: "%TOOL_BUILD_SCANPAYLOAD%"
  goto :fail
)
python "%TOOL_BUILD_SCANPAYLOAD%" "%REQUEST%" "%OUT_SCANRES%" "%OUT_EII%" "%OUT_SCANPAYLOAD%"
if errorlevel 1 goto :fail
echo [PIPELINE] OK -> wrote: "%OUT_SCANPAYLOAD%"

REM ------------------------------------------------------------
REM 4/9 Validate scan_payload schema
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 4/9 Validating scan_payload schema...
if exist "%TOOL_VALIDATE%" (
  if exist "%SCHEMA_SCANPAYLOAD%" (
    python "%TOOL_VALIDATE%" "%OUT_SCANPAYLOAD%" "%SCHEMA_SCANPAYLOAD%"
    if errorlevel 1 goto :fail
  ) else (
    echo [PIPELINE] WARN: scan_payload schema not found, skipping: "%SCHEMA_SCANPAYLOAD%"
  )
) else (
  echo [PIPELINE] WARN: validate_schema tool not found, skipping.
)

REM ------------------------------------------------------------
REM 5/9 Enforcing data policy (on scan_payload)
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 5/9 Enforcing data policy...
if exist "%TOOL_POLICY%" (
  python "%TOOL_POLICY%" "%OUT_SCANPAYLOAD%"
  if errorlevel 1 goto :fail
) else (
  echo [PIPELINE] WARN: enforce_policy tool not found, skipping: "%TOOL_POLICY%"
)

REM ------------------------------------------------------------
REM 6/9 Build cleanup proposal
REM cleanup_adapter.py expects: <payload.json> <eii_result.json> <out_cleanup_proposal.json>
REM We pass scan_payload as payload (not scan_request).
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 6/9 Building cleanup proposal (adapter)...
if not exist "%TOOL_ADAPTER%" (
  echo [PIPELINE] ERROR: cleanup_adapter not found: "%TOOL_ADAPTER%"
  goto :fail
)
python "%TOOL_ADAPTER%" "%OUT_SCANPAYLOAD%" "%OUT_EII%" "%OUT_PROPOSAL%"
if errorlevel 1 goto :fail
echo [PIPELINE] OK -> wrote: "%OUT_PROPOSAL%"

REM ------------------------------------------------------------
REM 7/9 Build command plan
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 7/9 Building command plan...
if not exist "%TOOL_BUILD_PLAN%" (
  echo [PIPELINE] ERROR: build_command_plan not found: "%TOOL_BUILD_PLAN%"
  goto :fail
)
python "%TOOL_BUILD_PLAN%" "%OUT_PROPOSAL%" "%OUT_PLAN%"
if errorlevel 1 goto :fail
echo [PIPELINE] OK -> wrote: "%OUT_PLAN%"

REM ------------------------------------------------------------
REM 8/9 Execute plan (dry-run)
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 8/9 Executing plan (dry-run)...
if not exist "%TOOL_DRYRUN%" (
  echo [PIPELINE] ERROR: execute_plan_dryrun not found: "%TOOL_DRYRUN%"
  goto :fail
)
python "%TOOL_DRYRUN%" "%OUT_PLAN%" "%OUT_EXEC%"
if errorlevel 1 goto :fail
echo [PIPELINE] OK -> wrote: "%OUT_EXEC%"

REM ------------------------------------------------------------
REM 9/9 Validate execution report schema (optional)
REM ------------------------------------------------------------
echo.
echo [PIPELINE] 9/9 Validating execution report schema...
if exist "%TOOL_VALIDATE%" (
  if exist "%SCHEMA_EXEC_REPORT%" (
    python "%TOOL_VALIDATE%" "%OUT_EXEC%" "%SCHEMA_EXEC_REPORT%"
    if errorlevel 1 goto :fail
  ) else (
    echo [PIPELINE] WARN: execution_report schema not found, skipping: "%SCHEMA_EXEC_REPORT%"
  )
) else (
  echo [PIPELINE] WARN: validate_schema tool not found, skipping.
)

echo.
echo [PIPELINE] DONE
exit /b 0

:fail
echo.
echo [PIPELINE] FAILED
exit /b 1
