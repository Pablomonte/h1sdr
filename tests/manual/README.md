# Manual Testing Suite - H1SDR v2.0

This directory contains manual test scripts for Phase 1 verification.

---

## Test Scripts

### 1. WebSocket Auto-Reconnect Test

**File:** `test_websocket_reconnect_manual.py`

**Purpose:** Verify that the RobustWebSocket implementation correctly handles
server disconnections and reconnects automatically.

**Duration:** ~15 minutes

**Prerequisites:**
- Server running (`python -m src.web_sdr.main_v2`)
- Browser open at http://localhost:8000
- Browser Developer Console visible

**Run:**
```bash
python tests/manual/test_websocket_reconnect_manual.py
```

**Tests:**
1. Initial connection verification
2. Server stop (auto-reconnect triggers)
3. Server restart (auto-recovery)
4. SDR data flow during reconnection
5. Streaming resume after reconnect
6. Message queuing (optional)

**Expected Results:**
- ✓ WebSocket reconnects automatically (no manual refresh)
- ✓ Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s (max)
- ✓ Messages queued while disconnected
- ✓ Queued messages sent on reconnect
- ✓ Streaming resumes after reconnection

---

### 2. 24-Hour Stability Test

**File:** `test_24hour_stability.py`

**Purpose:** Monitor system stability over 24 hours, collecting metrics on CPU,
memory, WebSocket health, and plugin performance.

**Duration:** 24 hours (can be interrupted)

**Prerequisites:**
- Server running (`python -m src.web_sdr.main_v2`)
- SDR started via web interface
- `aiohttp` and `psutil` installed

**Install dependencies:**
```bash
pip install aiohttp psutil
```

**Run:**
```bash
python tests/manual/test_24hour_stability.py
```

**Metrics Collected:**
- CPU usage (%, min/max/avg)
- Memory usage (%, MB)
- Disk usage (%)
- SDR running status
- FPS (frames per second)
- Plugin execution count
- Plugin failure count
- Health check success rate

**Output:**
- Console: Real-time metrics every 60 seconds
- File: `stability_test_metrics.jsonl` (JSON Lines format)

**Interruption:**
- Press Ctrl+C at any time to stop and generate report
- Partial results are valid for analysis

---

## Test Execution Guide

### Quick Test (WebSocket)

```bash
# Terminal 1: Start server
source venv/bin/activate
python -m src.web_sdr.main_v2

# Terminal 2: Run test
python tests/manual/test_websocket_reconnect_manual.py

# Follow on-screen instructions
```

### Long Test (24-Hour)

```bash
# Terminal 1: Start server
source venv/bin/activate
python -m src.web_sdr.main_v2

# Browser: http://localhost:8000
# Click "Start SDR"

# Terminal 2: Run test
python tests/manual/test_24hour_stability.py

# Let it run for 24 hours (or interrupt with Ctrl+C)
```

---

## Interpreting Results

### WebSocket Test

**Success criteria:**
- All 5 main tests pass
- Reconnection happens within 30 seconds
- No manual browser refresh needed
- Console shows clear reconnection messages

**Failure indicators:**
- Manual refresh required
- No reconnection after 60 seconds
- JavaScript errors in console
- Spectrum doesn't resume after reconnect

### 24-Hour Test

**Success criteria:**
- CPU usage avg < 20%
- Memory usage stable (no leaks)
- Plugin failures < 10 total
- Health check success rate > 99%
- FPS stable around target (e.g., 8-10 FPS)

**Failure indicators:**
- CPU usage > 50% sustained
- Memory usage increasing over time
- Plugin failures > 100
- Health check failures > 10
- FPS drops significantly

---

## Metrics Analysis

### CPU Usage

- **Excellent:** < 10% avg
- **Good:** 10-20% avg
- **Acceptable:** 20-50% avg
- **Poor:** > 50% avg

### Memory Usage

- **Excellent:** < 40% and stable
- **Good:** 40-60% and stable
- **Acceptable:** 60-80% and stable
- **Poor:** > 80% or increasing trend

### Plugin Failures

- **Excellent:** 0-5 over 24 hours
- **Good:** 5-20 over 24 hours
- **Acceptable:** 20-100 over 24 hours
- **Poor:** > 100 over 24 hours

### Health Checks

- **Excellent:** 100% success
- **Good:** > 99.5% success
- **Acceptable:** > 99% success
- **Poor:** < 99% success

---

## Troubleshooting

### WebSocket Test Issues

**Problem:** Reconnection not happening

**Solutions:**
1. Check browser console for errors
2. Verify websocket-manager.js is loaded
3. Check server logs for WebSocket errors
4. Ensure RobustWebSocket class is defined

**Problem:** Queued messages not sent

**Solutions:**
1. Check message queue size in RobustWebSocket
2. Verify onOpen callback flushes queue
3. Test with simple messages first

### 24-Hour Test Issues

**Problem:** High CPU usage

**Solutions:**
1. Check plugin processing times in stats
2. Reduce spectrum FPS in config
3. Verify FFTW threading is active
4. Check for infinite loops in plugins

**Problem:** Memory leaks

**Solutions:**
1. Check plugin buffer sizes (e.g., waterfall buffer)
2. Verify data structures are properly cleared
3. Monitor browser memory (separate issue)
4. Check for circular references

**Problem:** Test script crashes

**Solutions:**
1. Check server is accessible
2. Verify aiohttp/psutil installed
3. Check network connectivity
4. Review error messages in output

---

## Reporting Issues

When reporting test failures, include:

1. **Test name** (WebSocket or 24-hour)
2. **Duration run** (how long before failure)
3. **Error messages** (full traceback)
4. **Metrics log** (stability_test_metrics.jsonl if available)
5. **Server logs** (relevant portions)
6. **Browser console** (for WebSocket test)
7. **System info** (OS, Python version, hardware)

---

## Next Steps After Testing

### If WebSocket Test Passes ✓
1. Document reconnection behavior
2. Proceed to 24-hour stability test
3. Monitor for edge cases in production

### If 24-Hour Test Passes ✓
1. Analyze metrics trends
2. Identify optimization opportunities
3. Move to Phase 2 (Unit/E2E testing)
4. Prepare for production deployment

### If Tests Fail ✗
1. Review failure logs
2. Debug specific component
3. Re-run tests after fixes
4. Document issues and solutions

---

**Last Updated:** 2025-10-01
**Version:** 2.0.0
**Phase:** 1 Week 2 - Task 5
