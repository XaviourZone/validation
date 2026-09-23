# Portable PostgreSQL runtime

The Validation application will use an extracted PostgreSQL binary distribution, not an OS package installation.

Use separate binaries for each OS/architecture:

portable/
  windows-x64/
    bin/  postgres.exe, pg_ctl.exe, initdb.exe, psql.exe, ...
  linux-x64/
    bin/  postgres, pg_ctl, initdb, psql, ...
  data/
  start_postgres.bat
  start_postgres.sh
  stop_postgres.bat
  stop_postgres.sh

The binaries are OS-specific. The same PostgreSQL data directory must NOT be shared between Windows and Linux. Each machine keeps its own local data directory.

PostgreSQL pg_ctl can initialize, start, stop and report the status of a database cluster, and initdb creates that cluster.