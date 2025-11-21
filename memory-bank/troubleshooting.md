# Troubleshooting Guide - Traffic Safety Index System

Common issues and their solutions.

---

## Table of Contents
1. [Windows/Git Bash Issues](#windowsgit-bash-issues)
2. [Data Collection Problems](#data-collection-problems)
3. [Processing Errors](#processing-errors)
4. [API Issues](#api-issues)
5. [Docker/Container Issues](#dockercontainer-issues)
6. [Data Storage Problems](#data-storage-problems)

---

## Windows/Git Bash Issues

### Problem: Docker Commands Fail with Path Errors

**Symptom:**
```bash
$ docker exec trafficsafety-collector ls /app/data/parquet
ls: cannot access 'C:/Program Files/Git/app/data/parquet': No such file or directory
```

**Cause:** Git Bash automatically converts Unix paths to Windows paths

**Solution:** Prefix all Docker commands with `MSYS_NO_PATHCONV=1`

```bash
# ✅ Correct
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls /app/data/parquet

# ❌ Wrong
docker exec trafficsafety-collector ls /app/data/parquet
```

**Alternative:** Use PowerShell or CMD instead of Git Bash for Docker commands

---

## Data Collection Problems

### Problem: No Data Being Collected

**Symptom:**
```bash
$ docker-compose logs data-collector
✗ VCC API authentication failed - check credentials
```

**Solutions:**

1. **Check VCC Credentials:**
```bash
# View current credentials
cat backend/.env | grep VCC

# Verify they're not empty or placeholder values
VCC_CLIENT_ID=course-cs6604-student-djjay
VCC_CLIENT_SECRET=wHqQjvksKE6rYLYedkuIqewrFtEOpjHH
```

2. **Restart Collector:**
```bash
docker-compose restart data-collector
```

3. **Check VCC API Status:**
```bash
curl https://vcc.vtti.vt.edu/health
```

### Problem: Data Collector Keeps Restarting

**Symptom:**
```bash
$ docker-compose ps
trafficsafety-collector  Restarting
```

**Solutions:**

1. **Check Logs for Errors:**
```bash
docker-compose logs --tail=100 data-collector
```

2. **Common Causes:**
   - Missing Python dependencies: Rebuild image
   - Port conflicts: Check `COLLECTION_INTERVAL` setting
   - Permission issues: Check volume mounts

3. **Rebuild Container:**
```bash
docker-compose build data-collector
docker-compose up -d data-collector
```

### Problem: Collecting Data But Files Not Appearing

**Symptom:**
Logs show "✓ Saved X BSM messages" but files don't exist

**Solutions:**

1. **Check Volume Mount:**
```bash
docker volume ls | grep parquet
# Should show: cs6604-trafficsafety_parquet_data
```

2. **Verify Directory Structure:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -la /app/data/parquet/
# Should show: raw/, features/, indices/, constants/
```

3. **Check Disk Space:**
```bash
docker exec trafficsafety-collector df -h /app/data/
```

### Problem: Only Getting BSM Data, No PSM

**Symptom:**
```
✓ Collected 44 total BSM messages
✓ Collected 0 total PSM messages
```

**Explanation:** This is normal! PSM messages come from vulnerable road users (pedestrians, cyclists). If the area has no VRUs during collection, PSM count will be 0.

**Not a Problem:** The system works fine with BSM-only data.

---

## Processing Errors

### Problem: "No BSM data found. Cannot process."

**Symptom:**
```bash
$ python process_historical.py --days 1
[1/7] Loading raw data from Parquet files...
  Found 0 BSM files
✗ No BSM data found. Cannot process.
```

**Solutions:**

1. **Verify Data Collection is Running:**
```bash
docker-compose ps data-collector
# Should show: Up X minutes
```

2. **Check for BSM Files:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -l /app/data/parquet/raw/bsm/
```

3. **Wait for More Data:**
   - Historical processing requires at least 15 minutes of data
   - Wait for 15-20 collection cycles before processing

4. **Check Storage Path:**
```bash
# Make sure you're using the correct path
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --storage-path /app/data/parquet --days 1
```

### Problem: "KeyError: 'time_15min'"

**Symptom:**
```
KeyError: 'time_15min'
```

**Cause:** Feature extraction interval mismatch

**Solution:** This was fixed in the code. If you see this:

1. **Rebuild Container:**
```bash
docker-compose build data-collector
docker-compose up -d data-collector
```

2. **Verify Feature Engineering Code:**
Check that `vcc_feature_engineering.py` has the time column standardization:
```python
if time_col_name != 'time_15min':
    features['time_15min'] = features[time_col_name]
```

### Problem: Empirical Bayes Errors

**Symptom:**
```
KeyError: 'hour_of_day'
TypeError: apply_empirical_bayes() got an unexpected keyword argument 'baseline_rate'
```

**Solution:** Empirical Bayes is currently skipped. This is intentional and doesn't affect safety index computation.

**Workaround:** Raw safety indices are used (still meaningful)

**Future Fix:** Will be implemented when baseline data structure is corrected

### Problem: Processing Takes Too Long

**Symptom:** Historical processing runs for several minutes

**Causes:**
- Large dataset (> 7 days)
- Many intersections
- Slow I/O

**Solutions:**

1. **Reduce Lookback Period:**
```bash
# Instead of --days 7, use --days 1
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

2. **Process Specific Intersection:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 7 --intersection "0.0" --storage-path /app/data/parquet
```

3. **Check CPU/Memory:**
```bash
docker stats trafficsafety-collector
```

---

## API Issues

### Problem: API Returns safety_index: 0.0

**Symptom:**
```json
{
  "intersection_name": "0.0",
  "safety_index": 0.0,
  "traffic_volume": 26
}
```

**Cause:** Normalization constants haven't been computed yet

**Solution:** Run historical processing:
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

**Verify Constants Exist:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/constants/
# Should show: normalization_constants.parquet
```

### Problem: API Not Responding / Connection Refused

**Symptom:**
```bash
$ curl http://localhost:8001/health
curl: (7) Failed to connect to localhost port 8001
```

**Solutions:**

1. **Check API Container Status:**
```bash
docker-compose ps api
# Should show: Up X minutes (healthy)
```

2. **Check Logs:**
```bash
docker-compose logs api | tail -50
```

3. **Restart API:**
```bash
docker-compose restart api
```

4. **Check Port Binding:**
```bash
netstat -an | grep 8001
# Should show: LISTENING
```

### Problem: API Returns Empty Array []

**Symptom:**
```bash
$ curl http://localhost:8001/api/v1/safety/index/
[]
```

**Causes:**
- No processed indices available
- DATA_SOURCE not set to 'vcc'
- Parquet files not accessible

**Solutions:**

1. **Check DATA_SOURCE:**
```bash
cat backend/.env | grep DATA_SOURCE
# Should show: DATA_SOURCE=vcc
```

2. **Run Historical Processing:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

3. **Check Indices Files:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/indices/
```

---

## Docker/Container Issues

### Problem: Port Already in Use

**Symptom:**
```
Error starting userland proxy: listen tcp 0.0.0.0:8001: bind: address already in use
```

**Solutions:**

1. **Find Process Using Port:**
```bash
# Windows
netstat -ano | findstr :8001

# Kill process (replace PID)
taskkill /PID <PID> /F
```

2. **Change Port in docker-compose.yml:**
```yaml
ports:
  - "8002:8000"  # Changed from 8001 to 8002
```

### Problem: Containers Won't Start (Unhealthy)

**Symptom:**
```bash
$ docker-compose ps
trafficsafety-api  Up (unhealthy)
```

**Solutions:**

1. **Check Healthcheck Logs:**
```bash
docker inspect trafficsafety-api | grep -A 10 Health
```

2. **View Startup Logs:**
```bash
docker-compose logs api
```

3. **Rebuild Containers:**
```bash
docker-compose down
docker-compose up -d --build
```

### Problem: Volume Data Disappeared After Restart

**Symptom:** Parquet files missing after `docker-compose down`

**Cause:** Used `docker-compose down -v` which removes volumes

**Prevention:**
```bash
# ✅ Keeps data
docker-compose down

# ❌ Deletes data!
docker-compose down -v
```

**Recovery:** Data cannot be recovered if volumes were removed. Must collect new data.

### Problem: Docker Build Fails

**Symptom:**
```
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt"
```

**Solutions:**

1. **Check requirements.txt:**
```bash
cat backend/requirements.txt
```

2. **Rebuild with No Cache:**
```bash
docker-compose build --no-cache data-collector
```

3. **Check Docker Resources:**
   - Windows: Docker Desktop → Settings → Resources
   - Increase Memory to at least 4GB

---

## Data Storage Problems

### Problem: Disk Space Running Low

**Symptom:**
```
Error: No space left on device
```

**Solutions:**

1. **Check Disk Usage:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector du -sh /app/data/parquet/*
```

2. **Clean Old Parquet Files:**
```bash
# Remove BSM files older than 30 days
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector find /app/data/parquet/raw/bsm/ -name "*.parquet" -mtime +30 -delete
```

3. **Clean Docker System:**
```bash
docker system prune -a
```

### Problem: Parquet Files Corrupted

**Symptom:**
```
pyarrow.lib.ArrowInvalid: Parquet file size is 0 bytes
```

**Solutions:**

1. **Remove Corrupted File:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector rm /app/data/parquet/raw/bsm/bsm_2025-11-20_corrupt.parquet
```

2. **Rebuild Indices:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

### Problem: Permission Denied on Parquet Files

**Symptom:**
```
PermissionError: [Errno 13] Permission denied
```

**Solutions:**

1. **Check File Permissions:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -la /app/data/parquet/
```

2. **Fix Permissions:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector chmod -R 755 /app/data/parquet
```

---

## Debug Checklist

When troubleshooting any issue, run through this checklist:

### 1. Services Running?
```bash
docker-compose ps
```
All should show "Up" and "healthy"

### 2. Logs Clear?
```bash
docker-compose logs --tail=50
```
No errors or warnings?

### 3. Network Working?
```bash
docker network ls | grep trafficsafety
curl http://localhost:8001/health
```

### 4. Data Present?
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls /app/data/parquet/raw/bsm/
```
Files exist?

### 5. Configuration Correct?
```bash
cat backend/.env | grep -E "(VCC_|DATA_SOURCE)"
```
Credentials and settings correct?

---

## Getting Help

### Collect Debug Information

When reporting issues, include:

1. **System Info:**
```bash
docker --version
docker-compose --version
```

2. **Service Status:**
```bash
docker-compose ps
```

3. **Recent Logs:**
```bash
docker-compose logs --tail=100 data-collector > debug-collector.log
docker-compose logs --tail=100 api > debug-api.log
```

4. **Data Status:**
```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector find /app/data/parquet -name "*.parquet" | wc -l
```

5. **Configuration:**
```bash
cat backend/.env (redact secrets!)
```

### Common Log Patterns

**Success:**
```
✓ Retrieved 4 MapData messages
✓ Collected 44 BSM messages
✓ Saved 44 BSM messages
✓ Computed and saved safety indices for 1 intervals
```

**Authentication Error:**
```
✗ VCC API authentication failed - check credentials
```

**No Data:**
```
⚠ No new data collected
```

**Processing Error:**
```
✗ Error during collection cycle: ...
```

---

## Quick Fixes

| Problem | Quick Fix |
|---------|-----------|
| API returns 0.0 | Run historical processing |
| No data collected | Check VCC credentials, restart collector |
| Path errors (Windows) | Use `MSYS_NO_PATHCONV=1` prefix |
| Container won't start | `docker-compose down && docker-compose up -d --build` |
| Port in use | Change port in docker-compose.yml |
| Data disappeared | Check if you used `docker-compose down -v` |
| Slow processing | Reduce `--days` parameter |
| API not responding | `docker-compose restart api` |

---

**Last Updated**: 2025-11-20
**For More Help**: See `operational-guide.md` or check project documentation
