# Validation Data Forwarder

Final delivery service for the Validation pipeline.

`Data Router -> Data Parser -> Data Forwarder -> downstream`

The Forwarder consumes finalized XML files produced by the Parser. It does not parse AIS, correlate vessels, enrich reference data, or modify XML/business content.

## Current downstream

The configured operational destination is an SFTP/SSH destination. The host, SSH port, remote folder and username are stored in `config/forwarder.yaml`. The SSH password is stored locally in `state/forwarder_secrets.json` and is never committed to Git.

## Current implementation

- Persistent local delivery state in SQLite.
- Atomic XML spool files so a restart cannot consume a partially written file.
- Config-driven multiple destinations.
- Web Console add/edit/delete/enable/disable controls for destinations.
- Web Console connection/path test.
- Local filesystem delivery for offline integration testing.
- SFTP delivery through Paramiko using password or private-key authentication.
- Retry with configurable backoff.
- Duplicate protection using destination + output ID + SHA-256.
- Failed deliveries remain recorded and the original output is retained.
- HTTP telemetry endpoint.
- Graceful shutdown and systemd service definition.

## Credential setup

Open the Web Console -> **3. Data Forwarder** -> **Edit** for the configured destination and enter the SSH password. The password is written to the local owner-only credential file and is never returned by the telemetry API.

## Run

```text
python3 -m app.main --config config/forwarder.yaml
```

For an offline test, configure a `filesystem` destination. For production SFTP, install the approved Paramiko package from the offline package repository.
