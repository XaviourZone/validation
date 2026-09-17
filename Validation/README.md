# Validation Project

The **Validation** project is an enterprise-grade maritime domain awareness data pipeline designed to ingest, validate, correlate, enrich, and fuse disparate maritime and vessel feeds (AIS, radar, LRIT, pre-arrival notices, registry databases) into unified vessel track records and formatted XML streams.

---

## 1. Pipeline Stages

```
 1. INPUT
    ├── File Inflow (SAIS_IOR, SAIS_GLOBAL, MSIS, LRIT)
    └── Network Inflow (VATMS_EAST, VATMS_WEST, NAIS)
 2. DATA ROUTER           [ACTIVE IMPLEMENTATION]
 3. DATA PARSER           [PLANNED]
 4. NORMALIZATION         [PLANNED]
 5. VALIDATION            [PLANNED]
 6. CORRELATION           [PLANNED]
 7. REFERENCE ENRICHMENT  [PLANNED]
 8. FUSION                [PLANNED]
 9. FINAL DATA            [PLANNED]
10. XML GENERATION        [PLANNED]
11. FORWARDER             [PLANNED]
12. WEB CONTROL CONSOLE   [PLANNED]
```

---

## 2. Project Directory Structure

```
Validation/
│
├── DATA_ROUTER_DESIGN.txt     <- Living Master Specification for Data Router
├── DATA_PARSER_DESIGN.txt     <- Living Master Specification for Data Parser
├── FORWARDER_DESIGN.txt       <- Living Master Specification for Forwarder
│
├── SAMPLE_DATA/               <- Authoritative Reference Sample Data Repository
│   ├── SAIS/                  (SAIS_GLOBAL, SAIS_IOR CSVs)
│   ├── MSIS/                  (Decoded AIS CSVs)
│   ├── LRIT/                  (Positional CSVs)
│   ├── VATMS/                 (Coastal Radar feeds East/West)
│   ├── NAIS/                  (Shore station NMEA feeds)
│   ├── PANS/                  (BERMAN, CALINF, CALINV, VESPRO XMLs)
│   └── WRS/                   (White shipping datasets & decode files)
│
├── Data_Router/               <- PRODUCTION IMPLEMENTATION (Current Priority)
│   ├── app/
│   ├── config/
│   ├── docs/
│   ├── scripts/
│   ├── systemd/
│   └── tests/
│
├── Data_Parser/               <- Reserved for Phase 2
├── Validation_Engine/         <- Reserved
├── Correlation_Engine/        <- Reserved
├── Reference_Enrichment/      <- Reserved
├── Fusion_Engine/             <- Reserved
├── XML_Generator/             <- Reserved
├── Forwarder/                 <- Reserved
├── Web_Console/               <- Reserved
├── config/
├── logs/
├── state/
├── tests/
└── docs/
```

---

## 3. Project Continuity Rule

- When working on **Data Router**, always first review `DATA_ROUTER_DESIGN.txt` and the active code in `Data_Router/`.
- When working on **Data Parser**, always first review `DATA_PARSER_DESIGN.txt`.
- When working on **Forwarder**, always first review `FORWARDER_DESIGN.txt`.
- Treat `DESIGN.txt + SOURCE CODE + CONFIGURATION + TESTS + SAMPLE_DATA` as one continuous engineering project.
