# Validation — Data Router Service

Production-grade, long-running maritime data ingestion and routing service.

---

## 1. Pipeline Context

```
INPUT (File / TCP) ──► [DATA ROUTER] ──► DATA PARSER ──► ... ──► FORWARDER
```

The Data Router is strictly a **transport and routing layer**. It ingests maritime feeds, wraps each message in an ingestion envelope carrying source provenance, buffers items in a bounded queue with backpressure, and reliably delivers them to designated Data Parser endpoints (`:10001` - `:10005`).

---

## 2. Supported Ingestion Feeds

| Source | Input Type | Inflow Folder / Remote Endpoint | Parser Target | Port |
|--------|------------|---------------------------------|---------------|------|
| `SAIS_IOR` | File (CSV) | `DATA_INFLOW/SAIS_IOR` | SAIS Parser | `10001` |
| `SAIS_GLOBAL` | File (CSV) | `DATA_INFLOW/SAIS_GLOBAL` | SAIS Parser | `10001` |
| `MSIS` | File (CSV) | `DATA_INFLOW/MSIS` | MSIS Parser | `10002` |
| `LRIT` | File (CSV) | `DATA_INFLOW/LRIT` | LRIT Parser | `10003` |
| `VATMS_EAST` | TCP Stream | Configurable Remote Host:Port | VATMS Parser | `10004` |
| `VATMS_WEST` | TCP Stream | Configurable Remote Host:Port | VATMS Parser | `10004` |
| `NAIS` | TCP Stream | Configurable Remote Host:Port | NAIS Parser | `10005` |

---

## 3. Quickstart

### Prerequisites
- Python 3.10+
- PyYAML (`pip install -r requirements.txt`)

### Run the Service
```bash
python -m app.main --config config/sources.yaml
```

### Validate Configuration
```bash
python -m app.main --config config/sources.yaml --validate-config
```

### Check Service Status
```bash
python -m app.main --status
```
or query `http://127.0.0.1:8080/status` via browser or curl.

---

## 4. Running the Automated Test Suite

Execute the 26 unit and integration tests:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 5. Development Test Utilities

The `scripts/` directory provides utilities for testing before downstream Parsers are deployed:

- **Mock Parsers**: Listens on ports 10001–10005 and sends valid ACKs:
  ```bash
  python scripts/test_parser_receiver.py
  ```
- **Mock Feed Server**: Broadcasts streaming TCP test lines (VATMS/NAIS):
  ```bash
  python scripts/test_tcp_source.py --port 20001 --name VATMS_EAST
  ```
- **Test File Injector**: Drops test CSV files into `DATA_INFLOW` directories:
  ```bash
  python scripts/test_file_source.py --source SAIS_IOR
  ```

---

## 6. Architecture & Protocols
Detailed specifications can be found in `docs/`:
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — High-level architecture and data flow.
- [CONFIGURATION.md](docs/CONFIGURATION.md) — Complete configuration reference.
- [PROTOCOL.md](docs/PROTOCOL.md) — Wire framing and ACK protocol specification.
- [OPERATIONS.md](docs/OPERATIONS.md) — Production operations and troubleshooting.
