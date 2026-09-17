# Validation Web Console — Operator Console Walkthrough & Visual Diagrams

This document illustrates the upgraded Validation Web Console operator interface, the 3-service pipeline architecture, the safe configuration management workflows, and UI control layouts.

---

## 1. System Pipeline Architecture

```mermaid
graph TD
    subgraph INGESTION ["1. Ingestion Feeds"]
        SAIS_IOR["SAIS_IOR (File)"]
        SAIS_GLOBAL["SAIS_GLOBAL (File)"]
        MSIS["MSIS (File)"]
        LRIT["LRIT (File)"]
        VATMS_EAST["VATMS_EAST (TCP)"]
        VATMS_WEST["VATMS_WEST (TCP)"]
        NAIS["NAIS (TCP)"]
    end

    subgraph STAGE1 ["DATA ROUTER SERVICE (:8080)"]
        ROUTER_IN["Ingestion Threads"]
        Q["In-Memory Buffer Queue (10,000 Depth)"]
        STORE[("SQLite State Store")]
        DISPATCH["Dispatch Workers (x4)"]
        ROUTER_IN --> Q
        ROUTER_IN -.-> STORE
        Q --> DISPATCH
    end

    subgraph STAGE2 ["DATA PARSER SERVICE (:8081)"]
        P_SAIS["SAIS Decoder (:10001)"]
        P_MSIS["MSIS Decoder (:10002)"]
        P_LRIT["LRIT Decoder (:10003)"]
        P_VATMS["VATMS Decoder (:10004)"]
        P_NAIS["NAIS Decoder (:10005)"]
        
        INTERNAL["Data Parser Internal Engine
        • Parsing / Decoding
        • Normalization
        • Validation Logic
        • Vessel Correlation
        • Reference Enrichment (PANS/WRS/NSC)"]
        
        P_SAIS --> INTERNAL
        P_MSIS --> INTERNAL
        P_LRIT --> INTERNAL
        P_VATMS --> INTERNAL
        P_NAIS --> INTERNAL
    end

    subgraph STAGE3 ["DATA FORWARDER SERVICE"]
        FWD["Forwarder Runtime (NOT IMPLEMENTED)"]
    end

    subgraph DOWNSTREAM ["DOWNSTREAM SYSTEM"]
        DST["Downstream Consumer"]
    end

    SAIS_IOR --> ROUTER_IN
    SAIS_GLOBAL --> ROUTER_IN
    MSIS --> ROUTER_IN
    LRIT --> ROUTER_IN
    VATMS_EAST --> ROUTER_IN
    VATMS_WEST --> ROUTER_IN
    NAIS --> ROUTER_IN

    DISPATCH -->|TCP NDJSON + ACK| P_SAIS
    DISPATCH -->|TCP NDJSON + ACK| P_MSIS
    DISPATCH -->|TCP NDJSON + ACK| P_LRIT
    DISPATCH -->|TCP NDJSON + ACK| P_VATMS
    DISPATCH -->|TCP NDJSON + ACK| P_NAIS

    INTERNAL --> FWD
    FWD --> DST

    subgraph CONSOLE ["WEB CONSOLE (:8088)"]
        UI["Operator Web UI (Port 8088)"]
        CFG_MGR["RouterConfigManager (Atomic writes, RLock, Backup, Audit)"]
        CTRL["ServiceController (Windows dev / Linux systemd)"]
        UI <--> CFG_MGR
        UI <--> CTRL
        UI <-->|HTTP Telemetry| STAGE1
        UI <-->|HTTP Telemetry| STAGE2
    end
```

---

## 2. Operator Console Layout Diagram

```
+-------------------------------------------------------------------------------------------------------+
|  VALIDATION MARITIME OPERATIONS CONSOLE                             2026-09-17 10:20:00 UTC  [REFRESH]|
+-------------------------------------------------------------------------------------------------------+
| SIDEBAR      | DATA ROUTER OPERATIONAL CONSOLE                                                        |
|              |                                                                                        |
| Dashboard    | [Router Status: RUNNING]  [Throughput: 0.0 msg/s]  [Queue: 0 / 10000]  [ACKed: 0]      |
|              |                                                                                        |
| 1. Router *  | OPERATIONAL TOOLBARS:                                                                  |
| 2. Parser    | +---------------------+  +---------------------+  +---------------------+              |
| 3. Forwarder | | SERVICE CONTROL     |  | CONFIGURATION       |  | VIEW                |              |
|              | | [> Start] [■ Stop]  |  | [↺ Reload]          |  | [↻ Refresh]         |              |
| System       | | [⟳ Restart]         |  | [✓ Validate Config] |  |                     |              |
| Logs         | +---------------------+  +---------------------+  +---------------------+              |
|              |                                                                                        |
|              | DATA SOURCES                                                       [+ ADD DATA SOURCE] |
|              | +------------------------------------------------------------------------------------+ |
|              | | Source      | Enbl | Type | Input Config      | Parser | Destination | Status | Act| |
|              | |-------------+------+------+-------------------+--------+-------------+--------+----+ |
|              | | SAIS_IOR    | ENBL | FILE | folder: SAIS_IOR  | SAIS   | :10001      | ACTIVE | Edit |
|              | | SAIS_GLOBAL | ENBL | FILE | folder: SAIS_GLOB | SAIS   | :10001      | ACTIVE | Edit |
|              | | MSIS        | ENBL | FILE | folder: MSIS      | MSIS   | :10002      | ACTIVE | Edit |
|              | | LRIT        | ENBL | FILE | folder: LRIT      | LRIT   | :10003      | ACTIVE | Edit |
|              | | VATMS_EAST  | ENBL | TCP  | 127.0.0.1:20001   | VATMS  | :10004      | ACTIVE | Edit |
|              | | VATMS_WEST  | DISA | TCP  | 127.0.0.1:20002   | VATMS  | :10004      | DISABL | Edit |
|              | | NAIS        | DISA | TCP  | 127.0.0.1:20003   | NAIS   | :10005      | DISABL | Edit |
|              | +------------------------------------------------------------------------------------+ |
+-------------------------------------------------------------------------------------------------------+
```

---

## 3. Configuration Management & Validation Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Operator (Browser)
    participant UI as Web Console Frontend (:8088)
    participant API as Web Console Backend Server
    participant Mgr as RouterConfigManager
    participant Disk as sources.yaml / backup
    participant Router as Data Router Daemon (:8080)

    Note over Operator, Router: Scenario A: Non-Destructive Validation
    Operator->>UI: Click [✓ Validate Configuration]
    UI->>API: POST /api/router/sources/validate
    API->>Mgr: validate_source_payload()
    Mgr-->>API: (True, [], normalized_dict)
    API-->>UI: {valid: true, message: "Configuration is valid"}
    UI-->>Operator: Display green confirmation toast

    Note over Operator, Router: Scenario B: Add / Edit Source Workflow
    Operator->>UI: Click [+ ADD DATA SOURCE] or [Edit]
    UI->>UI: Hydrate modal fields & auto-derive destination
    Operator->>UI: Fill fields & Click [💾 Save Configuration]
    UI->>API: POST /api/router/sources/save
    API->>Mgr: save_source(payload)
    Note over Mgr: Acquire RLock
    Mgr->>Mgr: Semantic Validation
    Mgr->>Disk: Write sources.yaml.tmp & Verify
    Mgr->>Disk: Backup sources.yaml -> sources.yaml.bak
    Mgr->>Disk: Atomic replace (os.replace)
    Mgr->>Mgr: Emit Audit Log (CONFIG_SOURCE_UPDATED)
    Note over Mgr: Release RLock
    API-->>UI: {success: true, message: "Configuration saved. Reload required."}
    UI-->>Operator: Show toast: "Configuration saved. Reload required."

    Note over Operator, Router: Scenario C: Safe Operator-Triggered Reload
    Operator->>UI: Click [↺ Reload]
    UI->>API: POST /api/router/reload
    API->>Router: Reload configuration in-place
    Router-->>API: 200 OK
    API-->>UI: {success: true, message: "Router configuration reloaded"}
    UI-->>Operator: Display live updated telemetry
```

---

## 4. Dangerous Operation Safety Flow

```mermaid
stateDiagram-v2
    [*] --> OperatorClick: Operator clicks [■ Stop], [⟳ Restart], [Disable], or [Delete]
    OperatorClick --> InterceptModal: Intercepted by Confirmation Modal
    
    state InterceptModal {
        [*] --> WarningState: Display explicit hazard warning & entity name
        WarningState --> CancelClicked: Click [Cancel] or [✕]
        WarningState --> ConfirmClicked: Click [Confirm Action]
    }
    
    CancelClicked --> Aborted: No backend request emitted; UI restored
    ConfirmClicked --> ExecuteAction: Call backend API
    ExecuteAction --> AuditLogged: Emit audit log event
    AuditLogged --> SuccessToast: Display success toast & refresh telemetry
    SuccessToast --> [*]
    Aborted --> [*]
```
