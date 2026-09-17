# Data Router Service — Wire & ACK Protocol Specification
Version: 1.0
Status: Confirmed Baseline & Protocol Contract

## 1. Scope

This document specifies the wire format, message framing, delivery guarantees, error handling, and acknowledgement contract between the **Data Router Service** and downstream **Data Parser Services** (ports 10001–10005).

---

## 2. Protocol Versioning

All envelopes carry an explicit `protocol_version` field. The current baseline version is `"1.0"`.
Parsers must check this field. Minor additions within `1.x` will remain backward compatible.

---

## 3. Ingestion Envelope Schema

All data delivered from Data Router to a Data Parser is encapsulated in a JSON envelope.

### 3.1 Envelope Field Specification

| Field | Type | Required | Description |
|---|---|---|---|
| `protocol_version` | String | Yes | Protocol version identifier (currently `"1.0"`). |
| `message_id` | String | Yes | Globally unique deterministic or UUID identifier for delivery tracking. |
| `source` | String | Yes | Provenance source identifier (`SAIS_IOR`, `SAIS_GLOBAL`, `MSIS`, `LRIT`, `VATMS_EAST`, `VATMS_WEST`, `NAIS`). |
| `input_type` | String | Yes | `"FILE"` for folder/batch transfers, `"TCP"` for network stream lines. |
| `received_at` | String | Yes | ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SS.mmmmmm+00:00`). |
| `payload` | String | Yes | Raw unmodified payload (full file text for `FILE`, single sentence line for `TCP`). |
| `filename` | String | Conditional | Present if `input_type == "FILE"`. Base filename of the ingested file. |
| `file_size` | Integer | Conditional | Present if `input_type == "FILE"`. Total size in bytes (may be `0` for empty files). |
| `file_hash` | String | Conditional | Present if `input_type == "FILE"`. SHA-256 hexadecimal digest of the file bytes. |

### 3.2 File Ingestion Envelope Example
```json
{
  "protocol_version": "1.0",
  "message_id": "file:sais_ior:d3b07384d113edec49eaa6238ad5ff00",
  "source": "SAIS_IOR",
  "input_type": "FILE",
  "filename": "EarthIOR_2026-06-25-14-21-28.csv",
  "file_size": 708915,
  "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "received_at": "2026-09-17T00:15:30.123456+00:00",
  "payload": "\\s:66,c:1782377468*4C\\!AIVDM,1,1,,B,177hgW001bWc5el;kRfmHl@<00SR,0*47\n\\s:66,c:1782377469*4D\\!AIVDM,1,1,,A,18LKeB0PA27L3EJ0gKBLD?v>0851,0*76\n"
}
```

### 3.3 TCP Stream Envelope Example
```json
{
  "protocol_version": "1.0",
  "message_id": "tcp:vatms_east:f81d4fae7dec11d0a76500a0c91e6bf6",
  "source": "VATMS_EAST",
  "input_type": "TCP",
  "received_at": "2026-09-17T00:15:31.987654+00:00",
  "payload": "!WSVDM,1,1,1,A,1=JDkShP005p6<f9J=4rS8L60000,0*29"
}
```

---

## 4. Wire Framing Strategies

TCP is an unsegmented byte stream; message boundaries must be framed unambiguously.

### 4.1 Newline-Delimited JSON (NDJSON) [Default]
- The serialized UTF-8 JSON string is followed immediately by an ASCII newline (`\n` / `0x0A`).
- Any internal newlines inside the file payload are serialized with standard JSON escaping (`\n`).
- Parser reading rule: Buffer until encountering byte `0x0A`, then parse the accumulated buffer as UTF-8 JSON.

### 4.2 Length-Prefixed Framing [Optional]
- Frame layout:
  ```
  +--------------------------------+-------------------------------+
  |  Payload Length (4 bytes, BE)  |  UTF-8 JSON Envelope Bytes   |
  +--------------------------------+-------------------------------+
  ```
- 4-byte unsigned big-endian integer (`>I`) encoding byte length `N`, followed immediately by `N` bytes of UTF-8 JSON.

---

## 5. Parser Acknowledgement (ACK) Contract

Downstream parsers MUST acknowledge each received envelope over the same TCP connection.
Connecting alone is NOT an acknowledgement.

### 5.1 Positive ACK:
```json
{
  "message_id": "file:sais_ior:d3b07384d113edec49eaa6238ad5ff00",
  "status": "ACK",
  "timestamp": "2026-09-17T00:15:32.456789+00:00"
}
```

### 5.2 Negative ACK (NACK):
```json
{
  "message_id": "file:sais_ior:d3b07384d113edec49eaa6238ad5ff00",
  "status": "NACK",
  "error": "Parser schema validation failed or internal buffer full",
  "timestamp": "2026-09-17T00:15:32.456789+00:00"
}
```

---

## 6. Timeouts and Retry Behavior

- **Delivery Timeout**: Configured via `timeout_seconds` (default: `5.0s`). If an ACK is not returned within this window, the socket is disconnected and marked `TIMEOUT`.
- **Retry Policy**:
  - Exponential backoff with uniform random jitter:
    $$\text{delay} = \min(\text{max\_delay}, \text{initial\_delay} \times \text{multiplier}^{\text{attempt}-1}) \times \text{jitter}$$
    where jitter is drawn uniformly from $[0.8, 1.2]$.
  - `max_attempts`: Defaults to `5`.
  - State progression: `QUEUED` ➔ `SENDING` ➔ `RETRYING` (on error/timeout) ➔ `ACKNOWLEDGED` / `PROCESSED` (on success) or `FAILED` (after `max_attempts` exhausted).
- **Graceful Resumption**: If the Router or Parser crashes during `RETRYING`, the Router's startup recovery resets uncompleted file states to `DISCOVERED`, safely redelivering without data loss.

---

## 7. Operational Status & Health API

The Router provides an embedded HTTP API (default port 8080) for the future Web Control Console:
- `GET /health` / `GET /healthz`: Returns `{"status": "HEALTHY", "queue": "HEALTHY", "uptime_seconds": ...}`.
- `GET /status`: Returns composite status, per-destination connectivity, queue utilization %, and per-source operational counters.
- `GET /metrics`: Returns detailed operational counters (received, routed, acknowledged, failed, retries, rates, last error, last delivery).

---

## 8. PENDING SPECIFICATION

The following items cannot be fully resolved from current workspace sample files and are flagged as **PENDING SPECIFICATION** for future integration phases:

1. **Remote TCP Upstream Feed Authentication & Encryption**:
   - Status: `PENDING SPECIFICATION`
   - Details: `SAMPLE_DATA/VATMS/` and `SAMPLE_DATA/NAIS/` provide raw text recordings. Does the remote coastal radar or NAIS feed server require TLS/mTLS, basic auth, or token headers on initial TCP socket connection? Router currently assumes plain TCP stream as specified.
2. **Parser Connection Keep-Alive Lifecycle**:
   - Status: `PENDING SPECIFICATION`
   - Details: Whether parsers maintain long-lived TCP sessions across multiple hours or prefer connection cycling per batch. Router currently defaults to persistent sockets with automatic reconnection on disconnect (`keep_alive: true`).
3. **Parser Error Code Categorization**:
   - Status: `PENDING SPECIFICATION`
   - Details: Currently NACK responses contain an arbitrary error string. Whether future Data Parsers will emit structured error codes (e.g. `ERR_CORRUPT_PAYLOAD`, `ERR_BUFFER_OVERFLOW`) to differentiate non-retryable from retryable errors.

