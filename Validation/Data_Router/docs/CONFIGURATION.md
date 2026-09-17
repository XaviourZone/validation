# Data Router Service — Configuration Guide

## 1. Overview

The Data Router is completely configuration-driven via YAML. All input feeds, directories, network addresses, and downstream parser endpoints are managed through `config/sources.yaml`. Adding a new feed requires zero modifications to Python code.

---

## 2. Configuration Schema & Options

### 2.1 `data_inflow`
Base directory for file-based feeds.
```yaml
data_inflow:
  base_dir: "DATA_INFLOW" # Relative to workspace or absolute path
```

### 2.2 `parser_destinations`
Endpoints for downstream Data Parsers.
```yaml
parser_destinations:
  SAIS:
    host: "127.0.0.1"
    port: 10001
    framing: "ndjson" # Options: "ndjson" or "length_prefixed"
    timeout_seconds: 5.0
    keep_alive: true
```

### 2.3 `sources`
Definition of each maritime feed.

#### File Source Example:
```yaml
  SAIS_IOR:
    type: "file"
    folder: "SAIS_IOR"
    parser: "SAIS"
    enabled: true
    poll_interval_seconds: 1.0
    stability_window_seconds: 1.0
    file_patterns: ["*.csv", "*.txt", "*"]
    preserve_file: true
```

#### TCP Source Example:
```yaml
  VATMS_EAST:
    type: "tcp"
    remote_host: "10.0.1.25"
    remote_port: 20001
    parser: "VATMS"
    enabled: true
    framing: "line" # Options: "line", "length_prefixed"
    delimiter: "\n"
    max_line_length: 65536
    reconnect_initial_delay: 2.0
    reconnect_max_delay: 60.0
    reconnect_multiplier: 2.0
```

### 2.4 `retry`
Exponential backoff delivery policy.
```yaml
retry:
  max_attempts: 5
  initial_delay_seconds: 2.0
  max_delay_seconds: 60.0
  backoff_multiplier: 2.0
```

### 2.5 `queue`
Bounded in-memory buffer with backpressure.
```yaml
queue:
  max_size: 10000
  worker_count: 4
  high_watermark_ratio: 0.8
```

### 2.6 `monitoring`
Embedded HTTP status server.
```yaml
monitoring:
  enabled: true
  http_host: "127.0.0.1"
  http_port: 8080
```

### 2.7 `state`
Local SQLite operational database.
```yaml
state:
  db_path: "state/router_state.db"
```

---

## 3. Adding a New Source Tomorrow

To add a new coastal feed or CSV directory:
1. Open `config/sources.yaml`.
2. Add the source definition under `sources`:
```yaml
  NEW_COASTAL_RADAR:
    type: "tcp"
    remote_host: "192.168.10.50"
    remote_port: 30005
    parser: "VATMS"
    enabled: true
```
3. Validate configuration:
```bash
python -m app.main --config config/sources.yaml --validate-config
```
4. Restart or reload the service:
```bash
systemctl restart validation-router
```
Zero Python code changes are required.
