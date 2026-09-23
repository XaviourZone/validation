# Validation — PostgreSQL Single DB / Standalone Feed Scripts

This branch/package implements the requested architecture: one PostgreSQL database, one complete Python file per feed, and one database-manager Python file.

The executable package contains SAIS IOR, SAIS GLOBAL, MSIS, LRIT, VATMS East, VATMS West and NAIS source files plus `database_manager.py`.

Each feed file begins with editable `INPUT`, `ROUTER`, `DESTINATION`, `DATABASE` and reference-priority configuration, followed by all parsing, validation, correlation, fallback, 41-field normalization, XML generation, output and PostgreSQL audit/live-state logic.

WRS and NSC are imported into the same PostgreSQL database. WRS requires `Datasets/` and `Decode Files/`; NSC accepts CSV/XLSX and discovers the actual headers instead of inventing NSC fields. Imports are transactional full replacements.

The 41 XTrack logical fields and existing source-priority rules are retained. Unknown/unverified NSC fields and unavailable dimension components are left blank rather than fabricated.

See the downloadable standalone package for the complete runnable files.