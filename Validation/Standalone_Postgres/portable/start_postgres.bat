@echo off
setlocal
set ROOT=%~dp0
set PGROOT=%ROOT%windows-x64
set DATA=%ROOT%data
if not exist "%DATA%\PG_VERSION" "%PGROOT%\bin\initdb.exe" -D "%DATA%" -U validation -A scram-sha-256 -E UTF8
"%PGROOT%\bin\pg_ctl.exe" -D "%DATA%" -l "%ROOT%postgres.log" -o "-p 5432" start
endlocal
