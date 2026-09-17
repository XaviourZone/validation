# Data Router Service — Architecture Documentation

## 1. System Overview

The **Data Router Service** is the first operational stage in the **Validation** maritime processing pipeline:

```
INPUT SOURCES
     │
     ▼
[DATA ROUTER] ──► DATA PARSER ──► NORMALIZATION ──► VALIDATION ──► CORRELATION ──► ENRICHMENT ──► FUSION ──► FINAL DATA ──► XML GENERATOR ──► FORWARDER
```

The Data Router is strictly a **transport and routing layer**. It does **NOT** decode AIS sentences, inspect vessel fields (MMSI, IMO), perform correlation, or generate XML. Its single responsibility is reliable ingestion, provenance preservation, queuing, and delivery to designated parser endpoints.

---

## 2. High-Level Architecture Diagram

```
                        ┌──────────────────────────────┐
                        │   VALIDATION CONTROL CONSOLE │
                        └──────────────┬───────────────┘
                                       │ (HTTP Status API / Config)
                                       ▼
                        ┌──────────────────────────────┐
                        │     DATA ROUTER SERVICE      │
                        │        (app/main.py)         │
                        └──────────────┬───────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │                                                     │
            ▼                                                     ▼
   FILE INPUT MANAGER                                    TCP INPUT MANAGER
   (app/sources/file_source.py)                          (app/sources/tcp_source.py)
            │                                                     │
  ┌─────────┼─────────┬─────────┐                       ┌─────────┴─────────┐
  ▼         ▼         ▼         ▼                       ▼                   ▼
SAIS_IOR SAIS_GLOBAL MSIS      LRIT                 VATMS_EAST & WEST      NAIS
(Folder)  (Folder)  (Folder)  (Folder)              (TCP Stream Feeds)   (TCP Feed)
  │         │         │         │                       │                   │
  └─────────┴─────────┴─────────┴───────────┬───────────┴───────────────────┘
                                            │
                                            ▼
                                  INGESTION ENVELOPE
                                  - message_id (Deterministic/UUID)
                                  - source (Provenance)
                                  - input_type (FILE / TCP)
                                  - received_at (ISO-8601 UTC)
                                  - payload (Raw Data)
                                            │
                                            ▼
                                     ROUTING ENGINE
                                 (app/routing/router.py)
                                            │
                                            ▼
                                     BOUNDED QUEUE
                                  (Backpressure buffer)
                                            │
                                            ▼
                                     DELIVERY WORKERS
                               (ParserConnectionManager)
                                            │
              ┌──────────────┬──────────────┼──────────────┬──────────────┐
              ▼              ▼              ▼              ▼              ▼
           :10001         :10002         :10003         :10004         :10005
        SAIS Parser    MSIS Parser    LRIT Parser    VATMS Parser    NAIS Parser
```

---

## 3. Core Architectural Principles

### 3.1 Separation of Transport from Data Interpretation
- Data Router knows: source name, input type, file path, stability status, connection status, queue depth, destination host:port, delivery attempts, ACK status.
- Data Router does **NOT** know: MMSI, IMO, AIS message types, vessel names, geospatial boundaries, XML structure.

### 3.2 Provenance Preservation
Every piece of data is encapsulated in a `RoutingEnvelope` carrying the exact source identity (e.g. distinguishing `SAIS_IOR` from `SAIS_GLOBAL` and `VATMS_EAST` from `VATMS_WEST`), its reception timestamp, and original payload.

### 3.3 File Stability Detection
Before reading any file from disk:
1. Verifies file size and modification time remain invariant across `stability_window_seconds`.
2. Tests non-blocking read accessibility to ensure another process does not hold an exclusive write lock.
3. Only after stability confirmation is the file hashed and queued.

### 3.4 Persistent Deduplication (SQLite State Store)
State is stored in `state/router_state.db` (table `file_states`):
- Records `(source, filename, file_hash)` as primary key.
- Lifecycle states: `DISCOVERED` ➔ `WAITING_FOR_STABILITY` ➔ `READY` ➔ `QUEUED` ➔ `SENDING` ➔ `ACKNOWLEDGED` ➔ `PROCESSED`.
- On service restart, already acknowledged files are skipped immediately without re-transmission.

### 3.5 Fault Isolation & Automatic Reconnection
- Each TCP feed runs in an independent thread with exponential backoff reconnect logic.
- A failure or network disconnect on one source (e.g., VATMS_EAST offline) has zero effect on file polling or other TCP feeds.

### 3.6 Explicit Acknowledgement & Delivery Retries
- Router establishes socket connections to downstream Parsers.
- After transmitting an envelope, the delivery worker waits for an explicit ACK (`{"message_id": "...", "status": "ACK"}`).
- On timeout or network reset, items are rescheduled with exponential backoff and jitter up to `max_attempts`.

### 3.7 Crash Recovery & Interrupted Delivery Resumption
- When the service restarts, `reset_interrupted_states()` resets any `READY`, `QUEUED`, `SENDING`, or `RETRYING` records to `DISCOVERED`.
- In-flight deliveries interrupted by service termination or parser crashes safely resume without operator intervention.
- Acknowledged and processed records (`ACKNOWLEDGED`, `PROCESSED`) are preserved permanently to prevent duplicate re-transmission.

### 3.8 Scoped Deduplication
- Both persistent SQLite records and in-memory tracking sets are indexed by `(filename, file_hash)`.
- Multiple empty files (e.g. 0-byte cron outputs in LRIT/MSIS) or files with identical content arriving under distinct filenames are tracked independently and never mistakenly suppressed.

