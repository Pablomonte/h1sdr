#!/usr/bin/env python3
"""
Short-term Stability Test (10 minutes)

Monitors server health, WebSocket connections, and plugin stats
over a 10-minute period to validate stability before long-term testing.
"""

import asyncio
import json
import time
import sys
from pathlib import Path
from datetime import datetime
import subprocess

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def collect_metrics():
    """Collect system and application metrics"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "time": time.time()
    }

    # CPU usage
    try:
        cpu_result = subprocess.run(
            ["top", "-bn1"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in cpu_result.stdout.split('\n'):
            if 'Cpu(s)' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.endswith('us,'):  # user CPU
                        metrics["cpu_user_pct"] = float(parts[i][:-3])
                    elif part.endswith('sy,'):  # system CPU
                        metrics["cpu_system_pct"] = float(parts[i][:-3])
                    elif part.endswith('id,'):  # idle CPU
                        metrics["cpu_idle_pct"] = float(parts[i][:-3])
                break
    except Exception as e:
        print(f"Warning: Could not get CPU metrics: {e}")

    # Memory usage
    try:
        mem_result = subprocess.run(
            ["free", "-m"],
            capture_output=True,
            text=True,
            timeout=5
        )
        lines = mem_result.stdout.split('\n')
        if len(lines) > 1:
            mem_line = lines[1].split()
            total = int(mem_line[1])
            used = int(mem_line[2])
            metrics["mem_total_mb"] = total
            metrics["mem_used_mb"] = used
            metrics["mem_used_pct"] = (used / total) * 100 if total > 0 else 0
    except Exception as e:
        print(f"Warning: Could not get memory metrics: {e}")

    # Server health check
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8000/api/health"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            health = json.loads(result.stdout)
            metrics["server_status"] = health.get("status")
            metrics["sdr_connected"] = health.get("sdr_connected", False)
            metrics["active_connections"] = health.get("active_connections", 0)

            # Plugin stats
            plugin_sup = health.get("plugin_supervisor", {})
            metrics["plugin_executions"] = plugin_sup.get("total_executions", 0)
            metrics["plugin_failures"] = plugin_sup.get("total_failures", 0)
            metrics["plugin_failure_rate"] = plugin_sup.get("failure_rate", 0.0)

    except Exception as e:
        print(f"Warning: Could not get server health: {e}")
        metrics["server_status"] = "error"

    return metrics


async def run_stability_test(duration_minutes=10):
    """Run stability test for specified duration"""
    print("=" * 70)
    print(f"H1SDR v2.0 - Short-term Stability Test ({duration_minutes} minutes)")
    print("=" * 70)
    print()

    # Output file
    output_file = Path("/tmp/h1sdr_stability_short.jsonl")
    print(f"Metrics will be saved to: {output_file}")
    print()

    # Test parameters
    interval_seconds = 30  # Collect metrics every 30 seconds
    iterations = (duration_minutes * 60) // interval_seconds

    print(f"Test parameters:")
    print(f"  Duration: {duration_minutes} minutes")
    print(f"  Interval: {interval_seconds} seconds")
    print(f"  Total samples: {iterations}")
    print()

    # Initial metrics
    print("Collecting initial metrics...")
    initial = await collect_metrics()
    print(f"✓ Server status: {initial.get('server_status', 'unknown')}")
    print(f"✓ CPU: {initial.get('cpu_user_pct', 0):.1f}% user, "
          f"{initial.get('cpu_idle_pct', 0):.1f}% idle")
    print(f"✓ Memory: {initial.get('mem_used_mb', 0):.0f} MB / "
          f"{initial.get('mem_total_mb', 0):.0f} MB "
          f"({initial.get('mem_used_pct', 0):.1f}%)")
    print()

    # Write initial metrics
    with open(output_file, 'w') as f:
        f.write(json.dumps(initial) + '\n')

    # Start test
    start_time = time.time()
    print(f"Starting stability test at {datetime.now().strftime('%H:%M:%S')}")
    print(f"Will run until {datetime.fromtimestamp(start_time + duration_minutes * 60).strftime('%H:%M:%S')}")
    print()
    print("Press Ctrl+C to stop early (partial results will be saved)")
    print("-" * 70)

    try:
        for i in range(iterations):
            await asyncio.sleep(interval_seconds)

            # Collect metrics
            metrics = await collect_metrics()

            # Calculate elapsed time
            elapsed = time.time() - start_time
            remaining = (duration_minutes * 60) - elapsed
            progress = (elapsed / (duration_minutes * 60)) * 100

            # Write to file
            with open(output_file, 'a') as f:
                f.write(json.dumps(metrics) + '\n')

            # Progress update
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Progress: {progress:.1f}% | "
                  f"CPU: {metrics.get('cpu_user_pct', 0):.1f}% | "
                  f"Mem: {metrics.get('mem_used_pct', 0):.1f}% | "
                  f"Status: {metrics.get('server_status', 'unknown')} | "
                  f"Remaining: {remaining/60:.1f}min")

    except KeyboardInterrupt:
        print()
        print("Test interrupted by user")
        print()

    # Final metrics
    print("-" * 70)
    print("Collecting final metrics...")
    final = await collect_metrics()

    with open(output_file, 'a') as f:
        f.write(json.dumps(final) + '\n')

    # Analysis
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    # Read all metrics
    all_metrics = []
    with open(output_file, 'r') as f:
        for line in f:
            all_metrics.append(json.loads(line))

    if len(all_metrics) < 2:
        print("Not enough data for analysis")
        return

    # Calculate statistics
    cpu_user = [m.get('cpu_user_pct', 0) for m in all_metrics if 'cpu_user_pct' in m]
    mem_used = [m.get('mem_used_pct', 0) for m in all_metrics if 'mem_used_pct' in m]
    plugin_exec = [m.get('plugin_executions', 0) for m in all_metrics if 'plugin_executions' in m]
    plugin_fail = [m.get('plugin_failures', 0) for m in all_metrics if 'plugin_failures' in m]

    print()
    print(f"Samples collected: {len(all_metrics)}")
    print(f"Duration: {(final['time'] - initial['time']) / 60:.1f} minutes")
    print()

    if cpu_user:
        print(f"CPU Usage:")
        print(f"  Min: {min(cpu_user):.1f}%")
        print(f"  Max: {max(cpu_user):.1f}%")
        print(f"  Avg: {sum(cpu_user) / len(cpu_user):.1f}%")
    print()

    if mem_used:
        print(f"Memory Usage:")
        print(f"  Min: {min(mem_used):.1f}%")
        print(f"  Max: {max(mem_used):.1f}%")
        print(f"  Avg: {sum(mem_used) / len(mem_used):.1f}%")
    print()

    if plugin_exec:
        print(f"Plugin Activity:")
        print(f"  Total executions: {max(plugin_exec)}")
        print(f"  Total failures: {max(plugin_fail) if plugin_fail else 0}")
        if max(plugin_exec) > 0:
            failure_rate = (max(plugin_fail) / max(plugin_exec)) * 100
            print(f"  Failure rate: {failure_rate:.2f}%")
    print()

    # Health check
    server_ok = sum(1 for m in all_metrics if m.get('server_status') == 'ok')
    health_rate = (server_ok / len(all_metrics)) * 100
    print(f"Server Health:")
    print(f"  Healthy samples: {server_ok}/{len(all_metrics)} ({health_rate:.1f}%)")
    print()

    # Verdict
    print("=" * 70)
    if health_rate >= 95 and (not plugin_exec or max(plugin_fail) == 0):
        print("✓ STABILITY TEST PASSED")
        print()
        print("System is stable. Ready for long-term testing.")
    elif health_rate >= 90:
        print("⚠ STABILITY TEST: ACCEPTABLE")
        print()
        print("System is mostly stable with minor issues.")
    else:
        print("❌ STABILITY TEST FAILED")
        print()
        print("System shows instability. Investigate issues before long-term test.")

    print("=" * 70)
    print()
    print(f"Full metrics saved to: {output_file}")
    print()


if __name__ == "__main__":
    asyncio.run(run_stability_test(duration_minutes=10))
