# H1SDR v2.0 Implementation Plan

**Branch:** `v2-dev`
**Started:** 2025-10-01
**Based on:** [H1SDR-V2-ROADMAP.md](H1SDR-V2-ROADMAP.md)

---

## Branch Setup Complete ✓

- [x] Created `v2-dev` branch from `master`
- [x] Stashed pre-v2 work (audio fixes, frontend cleanup)
- [x] Created directory structure for all 4 phases
- [x] Initialized Phase 1 core implementations

---

## Phase 1: Core Performance (Weeks 1-2) - IN PROGRESS

### Week 1: Days 1-2 - FFTW Threading Optimization ⚡

**Implementation:** `src/web_sdr/dsp/fft_processor.py`

**Features:**
- Multi-threaded FFTW with up to 4 cores
- Pre-allocated aligned arrays for zero-copy
- Reusable FFTW plans (FFTW_MEASURE)
- Integrated benchmark suite
- Fallback to numpy.fft if pyfftw unavailable

**Target:** 3.3x speedup (2ms → 0.6ms per 4096-point FFT)

**Next Steps:**
1. Install pyfftw: `pip install pyfftw`
2. Run benchmark: `python -m src.web_sdr.dsp.fft_processor`
3. Verify acceptance criteria:
   - [x] 4-core threading enabled
   - [ ] Benchmark shows 2ms → 0.6ms improvement
   - [ ] Zero memory leaks over 1-hour run
   - [ ] CPU usage < 15% @ 20 FPS

---

### Week 1: Days 3-5 - WebSocket Auto-Reconnect 🔌

**Implementation:** `web/js/services/websocket-manager.js`

**Features:**
- Exponential backoff (1s → 30s max)
- Message queuing while disconnected (max 100 messages)
- Auto-flush on reconnect
- Support for binary and JSON messages
- Connection state tracking

**Acceptance Criteria:**
- [x] Exponential backoff implemented
- [x] Message queuing while disconnected
- [x] Auto-flush on reconnect
- [ ] No user intervention required (integration test)

**Next Steps:**
1. Integrate with existing WebSocket endpoints
2. Update frontend to use RobustWebSocket
3. Test with intentional network disconnections
4. 24-hour stability test

---

### Week 2: Supervisor Pattern + Fan-out Parallel 🛡️

**Implementation:** `src/web_sdr/pipeline/plugin_supervisor.py`

**Features:**
- Fan-out parallel execution (asyncio.gather)
- Error isolation (try/except per plugin)
- Detailed failure logging
- Per-plugin success/failure statistics
- Demonstration with example plugins

**Acceptance Criteria:**
- [x] Fan-out parallel (not sequential)
- [x] Plugin failures isolated
- [x] Acquisition never stops
- [x] Failure logging for debugging

**Next Steps:**
1. Create actual plugins (SpectrumProcessor, WaterfallUpdater, etc.)
2. Integrate with existing DSP pipeline
3. Add plugin registration system
4. Performance test with 2.4 MSPS IQ stream

---

## Directory Structure

```
h1sdr/
├── src/web_sdr/
│   ├── dsp/                    # Phase 1: DSP processing
│   │   └── fft_processor.py    ✓ FFTW threading
│   ├── pipeline/               # Phase 1: Plugin architecture
│   │   └── plugin_supervisor.py ✓ Supervisor pattern
│   ├── storage/                # Phase 3: HDF5 recording
│   ├── scanner/                # Phase 3: Adaptive scanner
│   ├── astronomy/              # Phase 4: Doppler correction
│   └── calibration/            # Phase 4: Manual calibration
├── web/js/services/
│   └── websocket-manager.js    ✓ Auto-reconnect
├── tests/
│   ├── unit/                   # Phase 2: Unit tests
│   ├── integration/            # Phase 2: Integration tests
│   └── e2e/                    # Phase 2: E2E tests (Playwright)
└── V2_IMPLEMENTATION_PLAN.md   ✓ This file
```

---

## Dependencies to Install

### Python (Phase 1)
```bash
pip install pyfftw  # FFTW threading
```

### Python (Phase 2-4)
```bash
pip install pytest pytest-asyncio pytest-cov  # Testing
pip install h5py  # HDF5 storage (Phase 3)
pip install astropy  # Doppler correction (Phase 4)
```

### JavaScript (Phase 2)
```bash
npm install --save-dev @playwright/test  # E2E testing
npm install --save-dev jest  # Unit testing
```

---

## Testing Strategy

### Phase 1 Testing (Manual)
- [x] FFTW benchmark script included
- [x] Supervisor demonstration script included
- [ ] WebSocket reconnect browser test

### Phase 2 Testing (Automated)
- [ ] Unit tests (pytest/jest) - 80% coverage target
- [ ] Integration tests (synthetic IQ data)
- [ ] E2E tests (Playwright) - critical flows
- [ ] CI/CD integration (GitHub Actions)

---

## Acceptance Criteria Summary

### Phase 1 Complete When:
- [ ] FFTW threading: 3.3x speedup measured
- [ ] WebSocket: 24-hour run with no manual reconnections
- [ ] Supervisor: Plugin crashes don't stop acquisition

### Phase 2 Complete When:
- [ ] CI/CD green on all tests
- [ ] 80%+ unit test coverage
- [ ] E2E tests for tune/record/export

### Phase 3 Complete When:
- [ ] 1-hour HDF5 recording < 5% CPU overhead
- [ ] Scanner finds narrowband signals with adaptive threshold

### Phase 4 Complete When:
- [ ] Manual calibration saves/loads profiles
- [ ] Doppler correction accurate to <1 kHz

---

## Roadmap References

- **Full Roadmap:** [H1SDR-V2-ROADMAP.md](H1SDR-V2-ROADMAP.md)
- **AI Debates:** [ARCHITECTURE-DEBATE-GROK.md](ARCHITECTURE-DEBATE-GROK.md)
- **Collaboration Summary:** [AI-COLLABORATION-COMPLETE-SUMMARY.md](AI-COLLABORATION-COMPLETE-SUMMARY.md)

---

**Status:** Phase 1 Week 1 implementations created, ready for testing
**Next Action:** Install pyfftw and run benchmarks
**Last Updated:** 2025-10-01
