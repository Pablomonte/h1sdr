#!/usr/bin/env python3
"""
Simple frequency control test without requiring SDR hardware
"""
import time
from websdr_automator import WebSDRAutomator


def test_frequency_input_only():
    """Test frequency control without starting SDR"""
    with WebSDRAutomator(headless=False) as sdr:
        print("\n🧪 Testing Frequency Control (No Hardware Required)")
        print("=" * 60)

        test_frequencies = [24.0, 50.0, 100.0, 433.0, 1420.4]

        for test_freq in test_frequencies:
            print(f"\n📻 Setting frequency to {test_freq:.4f} MHz")

            # Set frequency
            sdr.set_frequency(test_freq, wait_for_tune=False)
            time.sleep(0.5)

            # Read back from input field
            input_freq = sdr.get_frequency()
            print(f"   Input field shows: {input_freq:.4f} MHz")

            # Check spectrum display
            spectrum_freq = sdr.get_spectrum_frequency()
            if spectrum_freq:
                print(f"   Spectrum display: {spectrum_freq:.4f} MHz")
            else:
                print(f"   Spectrum display: Not yet initialized")

            # Verify input matches
            if abs(input_freq - test_freq) < 0.0001:
                print(f"   ✅ Input field correct!")
            else:
                print(f"   ❌ Input field mismatch: expected {test_freq:.4f}, got {input_freq:.4f}")
                sdr.screenshot(f"error_freq_{test_freq:.0f}_mhz.png")

        print("\n🎯 Test complete! Check if frequency display stays stable.")
        print("   Waiting 5 seconds to observe any unexpected changes...")
        time.sleep(5)

        final_freq = sdr.get_frequency()
        print(f"   Final frequency: {final_freq:.4f} MHz")

        if abs(final_freq - test_frequencies[-1]) < 0.0001:
            print("   ✅ Frequency stayed stable!")
        else:
            print(f"   ❌ Frequency changed unexpectedly to {final_freq:.4f} MHz")
            sdr.screenshot("error_frequency_drift.png")


if __name__ == '__main__':
    test_frequency_input_only()
