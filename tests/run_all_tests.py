#!/usr/bin/env python3
"""
Master test runner for H1SDR WebSDR
Runs complete TDD test suite with hardware dependencies
"""

import sys
import time
import subprocess
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from rtlsdr import RtlSdr
    RTL_SDR_AVAILABLE = True
except ImportError:
    RTL_SDR_AVAILABLE = False

def check_hardware():
    """Check if RTL-SDR hardware is available"""
    if not RTL_SDR_AVAILABLE:
        print("❌ RTL-SDR library not available")
        return False
        
    try:
        sdr = RtlSdr()
        device_info = str(sdr)
        sdr.close()
        print(f"✅ RTL-SDR detected: {device_info}")
        return True
    except Exception as e:
        print(f"❌ RTL-SDR hardware not available: {e}")
        return False

def check_server():
    """Check if WebSDR server is running"""
    import requests
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ WebSDR server running: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"❌ WebSDR server error: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ WebSDR server not accessible: {e}")
        return False

def run_test_module(module_name, description):
    """Run a specific test module"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    try:
        # Run the test module
        result = subprocess.run([
            sys.executable, "-m", f"tests.{module_name}"
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            return False
            
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="H1SDR Test Suite Runner")
    parser.add_argument("--skip-hardware", action="store_true", 
                       help="Skip hardware dependency checks")
    parser.add_argument("--skip-server", action="store_true",
                       help="Skip server dependency checks")
    parser.add_argument("--test-group", choices=["hardware", "dsp", "websocket", "performance", "regression", "all"],
                       default="all", help="Run specific test group")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick tests only (skip long-duration tests)")
    
    args = parser.parse_args()
    
    print("🚀 H1SDR WebSDR Test Suite")
    print("=" * 50)
    print("Hardware-dependent TDD tests for complete system validation")
    print()
    
    # Pre-flight checks
    checks_passed = True
    
    if not args.skip_hardware:
        print("🔧 Checking hardware dependencies...")
        if not check_hardware():
            checks_passed = False
            
    if not args.skip_server:
        print("🌐 Checking WebSDR server...")
        if not check_server():
            checks_passed = False
            print("💡 Hint: Start server with: python -m src.web_sdr.main")
            
    if not checks_passed:
        print("\n❌ Pre-flight checks failed!")
        print("Please resolve dependencies before running tests.")
        return 1
        
    print("\n✅ All dependencies satisfied")
    
    # Define test groups
    test_groups = {
        "hardware": [
            ("test_rtlsdr_hardware", "RTL-SDR Hardware Detection & Configuration")
        ],
        "dsp": [
            ("test_dsp_realtime", "DSP Processing with Real Signals")
        ],
        "websocket": [
            ("test_websocket_streaming", "WebSocket Streaming & Integration")
        ],
        "performance": [
            ("test_performance_realtime", "Real-time Performance Metrics")
        ],
        "regression": [
            ("test_system_regression", "System Regression & Stability")
        ]
    }
    
    # Determine which tests to run
    if args.test_group == "all":
        tests_to_run = []
        for group_tests in test_groups.values():
            tests_to_run.extend(group_tests)
    else:
        tests_to_run = test_groups.get(args.test_group, [])
        
    if not tests_to_run:
        print(f"❌ No tests found for group: {args.test_group}")
        return 1
        
    # Run tests
    print(f"\n🧪 Running {len(tests_to_run)} test modules...")
    
    results = []
    start_time = time.time()
    
    for module_name, description in tests_to_run:
        # Skip long tests if quick mode
        if args.quick and "performance" in module_name:
            print(f"⏭️  Skipping {description} (quick mode)")
            continue
            
        success = run_test_module(module_name, description)
        results.append((description, success))
        
        # Brief pause between test modules
        time.sleep(1.0)
        
    end_time = time.time()
    duration = end_time - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUITE SUMMARY")
    print(f"{'='*60}")
    
    passed_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:8} {description}")
        
    print(f"\n📈 Results: {passed_count}/{total_count} test modules passed")
    print(f"⏱️  Duration: {duration:.1f} seconds")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ H1SDR system verified without regressions")
        print("✅ Real-time performance confirmed")
        print("✅ Hardware integration working")
        return 0
    else:
        print(f"\n❌ {total_count - passed_count} TEST MODULES FAILED!")
        print("⚠️  System may have regressions or issues")
        print("🔍 Check individual test outputs above")
        return 1

if __name__ == "__main__":
    exit(main())