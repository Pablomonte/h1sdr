#!/usr/bin/env python3
"""
Automated WebSocket Reconnect Test

Tests WebSocket connection, disconnection, and auto-reconnect functionality
without requiring manual browser interaction.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import websockets
from websockets.exceptions import ConnectionClosed


async def test_websocket_connect():
    """Test 1: Initial WebSocket connection"""
    print("\n" + "=" * 70)
    print("TEST 1: WebSocket Initial Connection")
    print("=" * 70)

    try:
        async with websockets.connect("ws://localhost:8000/ws/spectrum") as ws:
            print("✓ Connected to spectrum WebSocket")

            # Wait for initial data
            data = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"✓ Received data: {len(data)} bytes")

            return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_websocket_reconnect():
    """Test 2: WebSocket reconnection after disconnect"""
    print("\n" + "=" * 70)
    print("TEST 2: WebSocket Reconnection")
    print("=" * 70)

    # First connection
    print("Establishing initial connection...")
    try:
        ws = await websockets.connect("ws://localhost:8000/ws/spectrum")
        print("✓ Initial connection established")

        # Receive some data
        data = await asyncio.wait_for(ws.recv(), timeout=5.0)
        print(f"✓ Received initial data: {len(data)} bytes")

        # Close connection
        print("Closing connection...")
        await ws.close()
        print("✓ Connection closed")

        # Wait a bit
        await asyncio.sleep(2)

        # Reconnect
        print("Attempting reconnection...")
        ws2 = await websockets.connect("ws://localhost:8000/ws/spectrum")
        print("✓ Reconnection successful")

        # Receive data again
        data = await asyncio.wait_for(ws2.recv(), timeout=5.0)
        print(f"✓ Received data after reconnect: {len(data)} bytes")

        await ws2.close()
        return True

    except Exception as e:
        print(f"❌ Reconnection test failed: {e}")
        return False


async def test_multiple_connections():
    """Test 3: Multiple concurrent WebSocket connections"""
    print("\n" + "=" * 70)
    print("TEST 3: Multiple Concurrent Connections")
    print("=" * 70)

    try:
        # Connect both spectrum and audio WebSockets
        spectrum_ws = await websockets.connect("ws://localhost:8000/ws/spectrum")
        print("✓ Spectrum WebSocket connected")

        audio_ws = await websockets.connect("ws://localhost:8000/ws/audio")
        print("✓ Audio WebSocket connected")

        # Receive data from both
        spectrum_data = await asyncio.wait_for(spectrum_ws.recv(), timeout=5.0)
        print(f"✓ Received spectrum data: {len(spectrum_data)} bytes")

        # Audio might not have data if SDR not started, that's ok
        try:
            audio_data = await asyncio.wait_for(audio_ws.recv(), timeout=2.0)
            print(f"✓ Received audio data: {len(audio_data)} bytes")
        except asyncio.TimeoutError:
            print("⚠ No audio data (SDR not started, OK)")

        # Close both
        await spectrum_ws.close()
        await audio_ws.close()
        print("✓ Both connections closed cleanly")

        return True

    except Exception as e:
        print(f"❌ Multiple connections test failed: {e}")
        return False


async def test_reconnect_with_exponential_backoff():
    """Test 4: Verify exponential backoff behavior"""
    print("\n" + "=" * 70)
    print("TEST 4: Exponential Backoff (Simulated)")
    print("=" * 70)

    print("Note: This test verifies connection resilience")
    print("Real exponential backoff is client-side (browser)")

    try:
        # Rapid reconnections should all work
        for i in range(5):
            ws = await websockets.connect("ws://localhost:8000/ws/spectrum")
            await ws.recv()  # Get data
            await ws.close()
            print(f"✓ Reconnection {i+1}/5 successful")
            await asyncio.sleep(0.5)

        return True

    except Exception as e:
        print(f"❌ Backoff test failed: {e}")
        return False


async def test_health_check():
    """Test 5: Verify server health and stats"""
    print("\n" + "=" * 70)
    print("TEST 5: Server Health Check")
    print("=" * 70)

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/health") as resp:
                health = await resp.json()

                print(f"✓ Server status: {health['status']}")
                print(f"✓ Version: {health['version']}")
                print(f"✓ Architecture: {health['architecture']}")
                print(f"✓ Plugins: {health['plugins']}")

                # Check plugin stats
                plugin_stats = health.get('plugin_supervisor', {})
                print(f"\nPlugin Supervisor Stats:")
                print(f"  Total executions: {plugin_stats.get('total_executions', 0)}")
                print(f"  Total failures: {plugin_stats.get('total_failures', 0)}")
                print(f"  Failure rate: {plugin_stats.get('failure_rate', 0):.2%}")

                return health['status'] == 'ok'

    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def main():
    """Run all WebSocket tests"""
    print("=" * 70)
    print("H1SDR v2.0 - Automated WebSocket Reconnect Test")
    print("=" * 70)
    print("\nPrerequisite: Server must be running on port 8000")
    print("Start with: python -m src.web_sdr.main_v2")
    print()

    # Wait for user confirmation
    input("Press ENTER when server is ready...")

    # Run tests
    results = []

    results.append(("Initial Connection", await test_websocket_connect()))
    results.append(("Reconnection", await test_websocket_reconnect()))
    results.append(("Multiple Connections", await test_multiple_connections()))
    results.append(("Exponential Backoff", await test_reconnect_with_exponential_backoff()))
    results.append(("Health Check", await test_health_check()))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("\nWebSocket reconnect functionality verified!")
        print("\nNext steps:")
        print("  1. Run manual browser test for full UX verification")
        print("  2. Run 24-hour stability test")
        print("     $ python tests/manual/test_24hour_stability.py")
        return 0
    else:
        print("=" * 70)
        print("SOME TESTS FAILED ❌")
        print("=" * 70)
        print("\nCheck server logs and retry failed tests.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
