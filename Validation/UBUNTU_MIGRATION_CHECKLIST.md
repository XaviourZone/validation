# Ubuntu Linux Offline Migration Checklist & Deployment Guide

This guide details the procedure for copying and deploying the **Validation System** (Data Router, Data Parser, and Web Console) from Windows development to an offline/air-gapped Ubuntu machine.

---

## 1. Migration Checklist

- [ ] Project copied to Ubuntu target directory (e.g. `/opt/validation`)
- [ ] Python version verified (Python 3.10+ installed)
- [ ] Dependencies installed offline (only `pyyaml` required)
- [ ] Configuration paths verified and environment set (`VALIDATION_HOME=/opt/validation`)
- [ ] System service user and permissions configured (`validation:validation`)
- [ ] Data Router systemd unit installed and started (`validation-router.service`)
- [ ] Data Parser systemd unit installed and started (`validation-parser.service`)
- [ ] Web Console systemd unit installed and started (`validation-web.service`)
- [ ] Router HTTP API reachable on `http://127.0.0.1:8080`
- [ ] Parser HTTP API reachable on `http://127.0.0.1:8081`
- [ ] Web Console UI reachable on `http://127.0.0.1:8088`
- [ ] Web Console displays live Data Router metrics and source table
- [ ] Web Console displays live Data Parser metrics and source distribution
- [ ] SAIS file ingestion verified (`SAIS_IOR` / `SAIS_GLOBAL` -> `:10001`)
- [ ] MSIS file ingestion verified (`MSIS` -> `:10002`)
- [ ] LRIT file ingestion verified (`LRIT` -> `:10003`)
- [ ] TCP feeds verified (`VATMS_EAST`, `VATMS_WEST` -> `:10004`, `NAIS` -> `:10005`)
- [ ] SQLite state database functioning (`router_state.db`)
- [ ] Log files updating cleanly (`router.log`, `parser.log`)
- [ ] Crash/restart recovery verified across systemd daemon restarts
- [ ] No Windows-specific path or dependency remaining (`C:\`, `\` paths)
- [ ] No internet connection required (100% air-gapped verified)

---

## 2. Directory Structure on Ubuntu

```text
/opt/validation/
├── Validation/
│   ├── DATA_ROUTER_DESIGN.txt
│   ├── DATA_PARSER_DESIGN.txt
│   ├── WEB_CONSOLE_DESIGN.txt
│   ├── FORWARDER_DESIGN.txt
│   ├── UBUNTU_MIGRATION_CHECKLIST.md
│   │
│   ├── Data_Router/
│   │   ├── app/
│   │   ├── config/sources.yaml
│   │   ├── logs/router.log
│   │   ├── state/router_state.db
│   │   ├── systemd/validation-router.service
│   │   └── requirements.txt
│   │
│   ├── Data_Parser/
│   │   ├── app/
│   │   ├── config/parser.yaml
│   │   ├── logs/parser.log
│   │   ├── systemd/validation-parser.service
│   │   └── requirements.txt
│   │
│   ├── Web_Console/
│   │   ├── app/
│   │   │   ├── static/ (css, js)
│   │   │   ├── templates/index.html
│   │   ├── config/console.yaml
│   │   ├── systemd/validation-web.service
│   │   └── requirements.txt
│   │
│   ├── DATA_INFLOW/          <-- Ingestion base folder for file sources
│   │   ├── SAIS_IOR/
│   │   ├── SAIS_GLOBAL/
│   │   ├── MSIS/
│   │   └── LRIT/
│   │
│   └── SAMPLE_DATA/          <-- Real validation samples
```

---

## 3. Step-by-Step Installation Commands

### Step 1: Create Dedicated Service User
```bash
sudo useradd -r -s /bin/false -d /opt/validation validation
```

### Step 2: Copy and Set Permissions
```bash
# Copy the project files
sudo mkdir -p /opt/validation
sudo cp -r Validation /opt/validation/

# Create required runtime directories
sudo mkdir -p /opt/validation/Validation/DATA_INFLOW/SAIS_IOR
sudo mkdir -p /opt/validation/Validation/DATA_INFLOW/SAIS_GLOBAL
sudo mkdir -p /opt/validation/Validation/DATA_INFLOW/MSIS
sudo mkdir -p /opt/validation/Validation/DATA_INFLOW/LRIT
sudo mkdir -p /opt/validation/Validation/Data_Router/logs
sudo mkdir -p /opt/validation/Validation/Data_Router/state
sudo mkdir -p /opt/validation/Validation/Data_Parser/logs

# Set ownership
sudo chown -R validation:validation /opt/validation
sudo chmod -R 750 /opt/validation
```

### Step 3: Offline Dependency Installation
All components use the Python standard library and pure bitwise arithmetic. The ONLY third-party dependency across the entire project is `pyyaml`.
To install offline:
```bash
# On internet-connected machine:
pip download pyyaml -d ./wheels/

# On offline Ubuntu machine:
pip3 install --no-index --find-links=./wheels/ pyyaml
```

### Step 4: Install Systemd Services
```bash
# 1. Install systemd service unit files
sudo cp /opt/validation/Validation/Data_Router/systemd/validation-router.service /etc/systemd/system/
sudo cp /opt/validation/Validation/Data_Parser/systemd/validation-parser.service /etc/systemd/system/
sudo cp /opt/validation/Validation/Web_Console/systemd/validation-web.service /etc/systemd/system/

# 2. Reload systemd daemon
sudo systemctl daemon-reload

# 3. Enable services on boot
sudo systemctl enable validation-router.service
sudo systemctl enable validation-parser.service
sudo systemctl enable validation-web.service

# 4. Start services in order: Parser -> Router -> Web Console
sudo systemctl start validation-parser.service
sudo systemctl start validation-router.service
sudo systemctl start validation-web.service
```

### Step 5: Verify Service Status and Ports
```bash
# Check service states
sudo systemctl status validation-parser.service
sudo systemctl status validation-router.service
sudo systemctl status validation-web.service

# Check listening ports
# Expected: 8080 (Router API), 8081 (Parser API), 8088 (Web Console), 10001-10005 (Parser TCP)
ss -tulpn | grep -E '8080|8081|8088|1000[1-5]'
```

### Step 6: Test Ingestion
```bash
# Copy a sample file into the active inflow directory
sudo cp /opt/validation/Validation/SAMPLE_DATA/SAIS/SAIS_IOR/EarthIOR_2026-06-25-14-21-28.csv \
  /opt/validation/Validation/DATA_INFLOW/SAIS_IOR/

# Inspect router log
sudo tail -f /opt/validation/Validation/Data_Router/logs/router.log

# Open Web Console in local browser:
# http://127.0.0.1:8088
```

---

## 4. Unrestricted OS Command Security
The Web Console communicates with the services via allow-listed API endpoints and the `LinuxSystemdController`. The web process does NOT have unrestricted root or shell execution privileges.
If the Web Console runs under the `validation` user and needs to execute `systemctl restart validation-router.service` without a password prompt, configure a scoped `sudoers` rule:
```text
# /etc/sudoers.d/validation-console
validation ALL=(ALL) NOPASSWD: /bin/systemctl start validation-router.service, /bin/systemctl stop validation-router.service, /bin/systemctl restart validation-router.service, /bin/systemctl reload-or-restart validation-router.service, /bin/systemctl status validation-router.service, /bin/systemctl start validation-parser.service, /bin/systemctl stop validation-parser.service, /bin/systemctl restart validation-parser.service
```
This strictly limits commands to allow-listed services without giving generic root shell access.
