# Data Router Service — Operations & Troubleshooting Guide

## 1. Service Management

### Linux systemd Service:
```bash
# Start service
sudo systemctl start validation-router

# Stop service
sudo systemctl stop validation-router

# Restart service
sudo systemctl restart validation-router

# Check status
sudo systemctl status validation-router

# View live systemd logs
journalctl -u validation-router -f
```

---

## 2. CLI Commands

From the project root:

```bash
# Run service in foreground
python -m app.main --config config/sources.yaml

# Validate configuration syntax and endpoints
python -m app.main --config config/sources.yaml --validate-config

# Query local status endpoint
python -m app.main --status

# Print version
python -m app.main --version
```

---

## 3. Monitoring & Health Status API

When running, the router exposes an embedded HTTP server (default `http://127.0.0.1:8080`):

### Query Health:
```bash
curl -s http://127.0.0.1:8080/health
```
Response:
```json
{
  "status": "HEALTHY",
  "queue": "HEALTHY",
  "uptime_seconds": 3600.5
}
```

### Query Full Operational Status:
```bash
curl -s http://127.0.0.1:8080/status
```
Response includes:
- Queue depth, capacity, and congestion percentage
- Connectivity status of each parser destination (10001–10005)
- Per-source metrics (files discovered/processed/failed, message rates, last error)

---

## 4. Troubleshooting & Log Analysis

Log file: `logs/router.log` (rotating 10MB x 5 backups).

### Common Log Events:
| Event | Meaning | Operational Action |
|-------|---------|-------------------|
| `file_detected` | New file detected in monitored folder | Normal operation |
| `waiting_for_stability` | File is currently being written | Normal; will be processed once stable |
| `queued` | Enveloped and queued for delivery | Normal operation |
| `sending` | Transmitting to downstream parser | Normal operation |
| `acknowledged` | Downstream parser returned valid ACK | Delivery successful |
| `file_skipped_duplicate` | File already in state database | Prevents duplicate processing |
| `delivery_failed_retrying` | Downstream parser unreachable or timed out | Verify parser service on destination port |
| `delivery_exhausted_failed` | Max retries reached; file recorded as failed | Check network routing / parser availability |
| `connection_lost` | Remote TCP feed disconnected | Automatic backoff reconnect is active |
| `interrupted_states_reset` | Uncompleted files reset on startup | Crash recovery: in-flight files safely resuming |

---

## 5. Offline Deployment

To deploy on an air-gapped Linux machine:
1. Ensure Python 3.10+ is installed.
2. Transfer `PyYAML` wheel or install via local pip cache:
   ```bash
   pip install --no-index --find-links=/path/to/wheels -r requirements.txt
   ```
3. Copy `systemd/validation-router.service` to `/etc/systemd/system/`.
4. Run `sudo systemctl daemon-reload && sudo systemctl enable validation-router`.
