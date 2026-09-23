# Validation - single PostgreSQL database

There is one PostgreSQL database. It is NOT an application-state database.

PostgreSQL stores only:
1. WRS reference data.
2. PANS reference data.
3. NSC reference data.
4. UN/LOCODE reference data used for destination resolution.
5. The current live parsed result needed by the system: source ID, UN/LOCODE and current XML/live-monitoring information required by the console.

Previous application events, parser history, raw XML history, processing logs and service heartbeats are not stored in PostgreSQL.

The console's process/file monitoring state is local runtime information.

## Source programs

Each feed has one self-contained Python program. The editable configuration is at the top:

INPUT -> ROUTER -> DATABASE -> REFERENCE -> PARSER -> XML -> DESTINATION

Current project inputs are SAIS_IOR, SAIS_GLOBAL, MSIS, LRIT, VATMS_EAST, VATMS_WEST and NAIS. Each source keeps its source-specific decoder/parser and uses the common reference/fallback/XML logic already established in the project.

## Reference priority

Incoming source values remain primary when present. Missing fields are filled using the established WRS/PANS/NSC logic. UN/LOCODE is used only for destination-code resolution. No value is invented when no source/reference value exists.

## Console

database_manager.py is the single database/console program. It will show:
- PostgreSQL status
- WRS status and last update
- PANS status and last update
- NSC status and last update
- UN/LOCODE status and last update
- each source program running/stopped state from local runtime status files
- input folder and XML destination/last XML activity

It provides folder selection/import for WRS and equivalent reference import for NSC/PANS/UN/LOCODE.

## Portable PostgreSQL

Do not install PostgreSQL as a Windows service or Ubuntu package for this application. Ship OS-specific extracted PostgreSQL binaries with the application.

Windows uses the Windows ZIP binaries.
Ubuntu/Linux uses Linux binaries.

The data directory is local to that OS. initdb creates it and pg_ctl starts/stops it.

Do NOT copy a Windows PostgreSQL data directory to Linux or vice versa.

The official PostgreSQL Windows download page documents a ZIP archive of binaries without the installer. PostgreSQL documents pg_ctl/initdb for initializing and controlling a database cluster.
