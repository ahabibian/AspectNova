@echo off
for /f "usebackq delims=" %%S in (`python -c "import sysconfig; print(sysconfig.get_path('scripts'))"`) do set "SCRIPTS=%%S"
"%SCRIPTS%\aspectnova.exe" %*
exit /b %ERRORLEVEL%