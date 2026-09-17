# Validation Data Forwarder

Final delivery service for the Validation pipeline.

`Data Router -> Data Parser -> Data Forwarder -> downstream`

The Forwarder consumes finalized XML files produced by the Parser. It does not parse AIS, correlate vessels, enrich reference data, or modify XML/business content.

## Current implementation

- Persistent local delivery state in SQLite.
- Atomic XML spool files so a restart cannot consume a partially written file.
- Config-driven destinations.
- Local filesystem delivery for offline integration testing.
- SFTP delivery through Paramiko when the downstream specification requires SSH/SFTP.
- Retry with configurable backoff.
- Duplicate protection using destination + output ID + SHA-256.
- Failed deliveries remain recorded and the original output is retained.
- HTTP telemetry endpoint.
- Graceful shutdown and systemd service definition.

The exact production downstream host, port, remote path and authentication reference are intentionally configuration values. They are not hard-coded because the project design does not define those values.

## Run

```text
python3 -m app.main --config config/forwarder.yaml
```

For an offline test, configure a `filesystem` destination. For production SFTP, install the pinned Paramiko dependency from the approved offline package repository and configure the credential reference outside Git.
