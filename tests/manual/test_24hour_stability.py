#!/usr/bin/env python3
"""
24-Hour Stability Test for H1SDR v2.0

This script monitors the WebSDR system for 24 hours, collecting metrics
on CPU usage, memory, WebSocket reconnections, and plugin performance.
"""

import asyncio
import aiohttp
import time
import psutil
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque

print("=" * 70)
print("H1SDR v2.0 - 24-Hour Stability Test")
print("=" * 70)
print()

# Configuration
SERVER_URL = "http://localhost:8000"
CHECK_INTERVAL = 60  # Check every 60 seconds
DURATION_HOURS = 24
METRICS_LOG = Path("stability_test_metrics.jsonl")

# Metrics storage
metrics_history = deque(maxlen=1440)  # Store last 24 hours (1 per minute)
start_time = None


class StabilityMonitor:
    """Monitor system stability metrics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.metrics = []
        self.websocket_reconnects = 0
        self.plugin_failures = 0
        self.total_checks = 0
        self.failed_checks = 0

    async def check_server_health(self):
        """Check server health endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SERVER_URL}/api/health", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return True, data
                    else:
                        return False, None
        except Exception as e:
            return False, str(e)

    async def check_sdr_status(self):
        """Check SDR status"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{SERVER_URL}/api/sdr/status", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return True, data.get('data', {})
                    else:
                        return False, None
        except Exception as e:
            return False, str(e)

    def get_system_metrics(self):
        """Get system-level metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_mb = memory.used / (1024 * 1024)

            # Disk I/O
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'memory_mb': memory_mb,
                'disk_percent': disk_percent
            }
        except Exception as e:
            print(f"Error getting system metrics: {e}")
            return None

    async def collect_metrics(self):
        """Collect all metrics for this interval"""
        self.total_checks += 1
        timestamp = datetime.now()

        # Check server health
        health_ok, health_data = await self.check_server_health()
        if not health_ok:
            self.failed_checks += 1
            print(f"❌ [{timestamp}] Health check failed: {health_data}")
            return None

        # Check SDR status
        sdr_ok, sdr_data = await self.check_sdr_status()

        # Get system metrics
        system_metrics = self.get_system_metrics()

        # Extract plugin supervisor stats
        plugin_stats = None
        if sdr_data and 'plugin_supervisor' in sdr_data:
            plugin_stats = sdr_data['plugin_supervisor']
            total_failures = plugin_stats.get('total_failures', 0)
            if total_failures > self.plugin_failures:
                new_failures = total_failures - self.plugin_failures
                self.plugin_failures = total_failures
                print(f"⚠️  [{timestamp}] Plugin failures detected: {new_failures} new, {total_failures} total")

        # Compile metrics
        metrics = {
            'timestamp': timestamp.isoformat(),
            'uptime_hours': (timestamp - self.start_time).total_seconds() / 3600,
            'health': {
                'status': health_data.get('status') if health_data else None,
                'sdr_connected': health_data.get('sdr_connected') if health_data else False,
                'active_connections': health_data.get('active_connections') if health_data else 0,
                'plugins': health_data.get('plugins') if health_data else 0
            },
            'system': system_metrics,
            'sdr': {
                'running': sdr_data.get('running') if sdr_data else False,
                'center_frequency': sdr_data.get('center_frequency') if sdr_data else None,
                'fps': sdr_data.get('stats', {}).get('fps') if sdr_data else 0
            },
            'plugins': plugin_stats,
            'checks': {
                'total': self.total_checks,
                'failed': self.failed_checks,
                'success_rate': (self.total_checks - self.failed_checks) / self.total_checks if self.total_checks > 0 else 0
            }
        }

        self.metrics.append(metrics)
        return metrics

    def save_metrics(self, metrics):
        """Save metrics to file"""
        try:
            with open(METRICS_LOG, 'a') as f:
                f.write(json.dumps(metrics) + '\n')
        except Exception as e:
            print(f"Error saving metrics: {e}")

    def print_summary(self, metrics):
        """Print current metrics summary"""
        uptime = metrics['uptime_hours']
        cpu = metrics['system']['cpu_percent']
        mem = metrics['system']['memory_percent']
        fps = metrics['sdr']['fps']
        running = metrics['sdr']['running']

        plugin_failures = 0
        plugin_executions = 0
        if metrics['plugins']:
            plugin_failures = metrics['plugins'].get('total_failures', 0)
            plugin_executions = metrics['plugins'].get('total_executions', 0)

        print(f"[{metrics['timestamp']}] "
              f"Uptime: {uptime:.1f}h | "
              f"CPU: {cpu:.1f}% | "
              f"Mem: {mem:.1f}% | "
              f"FPS: {fps:.1f} | "
              f"Running: {running} | "
              f"Plugins: {plugin_executions} exec, {plugin_failures} fail | "
              f"Checks: {self.total_checks}/{self.failed_checks}")

    def print_final_report(self):
        """Print final stability test report"""
        print("\n" + "=" * 70)
        print("24-HOUR STABILITY TEST REPORT")
        print("=" * 70)
        print()

        duration = datetime.now() - self.start_time
        print(f"Test Duration: {duration}")
        print(f"Total Checks: {self.total_checks}")
        print(f"Failed Checks: {self.failed_checks}")
        print(f"Success Rate: {(self.total_checks - self.failed_checks) / self.total_checks * 100:.2f}%")
        print()

        # Analyze metrics
        if self.metrics:
            cpu_values = [m['system']['cpu_percent'] for m in self.metrics if m['system']]
            mem_values = [m['system']['memory_percent'] for m in self.metrics if m['system']]
            fps_values = [m['sdr']['fps'] for m in self.metrics if m['sdr']['fps'] > 0]

            print("SYSTEM METRICS:")
            print("-" * 70)
            if cpu_values:
                print(f"CPU Usage:")
                print(f"  Min:  {min(cpu_values):.1f}%")
                print(f"  Max:  {max(cpu_values):.1f}%")
                print(f"  Avg:  {sum(cpu_values) / len(cpu_values):.1f}%")
            if mem_values:
                print(f"Memory Usage:")
                print(f"  Min:  {min(mem_values):.1f}%")
                print(f"  Max:  {max(mem_values):.1f}%")
                print(f"  Avg:  {sum(mem_values) / len(mem_values):.1f}%")
            if fps_values:
                print(f"FPS:")
                print(f"  Min:  {min(fps_values):.1f}")
                print(f"  Max:  {max(fps_values):.1f}")
                print(f"  Avg:  {sum(fps_values) / len(fps_values):.1f}")
            print()

            print("PLUGIN PERFORMANCE:")
            print("-" * 70)
            print(f"Total Plugin Failures: {self.plugin_failures}")
            print()

        print("RECOMMENDATIONS:")
        print("-" * 70)
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
        avg_mem = sum(mem_values) / len(mem_values) if mem_values else 0

        if avg_cpu > 50:
            print("⚠️  High CPU usage detected (avg > 50%)")
        elif avg_cpu > 20:
            print("⚠️  Moderate CPU usage (avg > 20%)")
        else:
            print("✓ CPU usage acceptable")

        if avg_mem > 80:
            print("⚠️  High memory usage detected (avg > 80%)")
        elif avg_mem > 60:
            print("⚠️  Moderate memory usage (avg > 60%)")
        else:
            print("✓ Memory usage acceptable")

        if self.plugin_failures > 100:
            print("⚠️  High plugin failure count (> 100)")
        elif self.plugin_failures > 10:
            print("⚠️  Moderate plugin failures detected")
        else:
            print("✓ Plugin stability excellent")

        if self.failed_checks > 10:
            print("⚠️  Multiple health check failures detected")
        elif self.failed_checks > 0:
            print("⚠️  Some health check failures")
        else:
            print("✓ All health checks passed")

        print()
        print("=" * 70)
        print(f"Metrics saved to: {METRICS_LOG}")
        print("=" * 70)


async def main():
    """Main test loop"""
    print("PREREQUISITES:")
    print("-" * 70)
    print("1. Server must be running: python -m src.web_sdr.main_v2")
    print("2. SDR should be started via web interface")
    print("3. This test will run for 24 hours")
    print()

    response = input("Is the server running and SDR started? (y/n): ")
    if response.lower() != 'y':
        print("Please start the server and SDR first, then re-run this test.")
        sys.exit(1)

    print()
    print("Starting 24-hour stability test...")
    print(f"Metrics will be logged to: {METRICS_LOG}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print()

    monitor = StabilityMonitor()
    end_time = datetime.now() + timedelta(hours=DURATION_HOURS)

    try:
        while datetime.now() < end_time:
            # Collect metrics
            metrics = await monitor.collect_metrics()

            if metrics:
                # Save to file
                monitor.save_metrics(metrics)

                # Print summary
                monitor.print_summary(metrics)

            # Wait for next interval
            await asyncio.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
    finally:
        # Print final report
        monitor.print_final_report()


if __name__ == '__main__':
    print()
    print("IMPORTANT: This test will run for 24 hours!")
    print("You can interrupt it at any time with Ctrl+C to see current results.")
    print()
    response = input("Continue with 24-hour test? (y/n): ")

    if response.lower() == 'y':
        asyncio.run(main())
    else:
        print("Test cancelled.")
