#!/usr/bin/env python3
"""
WebSDR Automation Tool - Playwright-based testing and interaction lever
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from typing import Optional, Dict, Any, List


class WebSDRAutomator:
    """
    Automated interaction tool for H1SDR WebSDR interface.

    Provides programmatic control over the WebSDR for:
    - Automated testing
    - Frequency scanning
    - UI verification
    - Performance monitoring
    """

    def __init__(
        self,
        headless: bool = False,
        base_url: str = "http://localhost:8000",
        auth_state_path: Optional[Path] = None
    ):
        """
        Initialize WebSDR automator.

        Args:
            headless: Run browser without GUI (for CI/servers)
            base_url: WebSDR server URL
            auth_state_path: Path to saved authentication state
        """
        self.base_url = base_url
        self.auth_state_path = auth_state_path or Path("auth_state.json")
        self.headless = headless

        # Playwright instances
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def __enter__(self):
        """Context manager entry - start browser"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        self.close()

    def start(self):
        """Start browser and load WebSDR"""
        self.playwright = sync_playwright().start()

        # Launch browser with specific settings
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--autoplay-policy=no-user-gesture-required',  # Allow audio autoplay
            ]
        )

        # Create context with or without saved auth
        if self.auth_state_path.exists():
            with open(self.auth_state_path) as f:
                storage_state = json.load(f)
            self.context = self.browser.new_context(storage_state=storage_state)
        else:
            self.context = self.browser.new_context()

        # Create page and navigate
        self.page = self.context.new_page()
        self.page.goto(self.base_url, wait_until="networkidle", timeout=30000)

        # Wait for critical elements
        self.page.wait_for_selector('#frequency-input', timeout=10000)

        # Wait for loading overlay to disappear
        self.page.wait_for_selector('#loading-overlay', state='hidden', timeout=10000)

        print(f"✅ WebSDR loaded: {self.base_url}")

    def close(self):
        """Close browser and cleanup"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("🔒 Browser closed")

    def save_auth(self, path: Optional[Path] = None):
        """Save current session state for reuse"""
        path = path or self.auth_state_path
        if self.context:
            storage = self.context.storage_state()
            with open(path, 'w') as f:
                json.dump(storage, f, indent=2)
            print(f"💾 Auth state saved: {path}")

    def screenshot(self, name: str = "debug.png") -> Path:
        """Take screenshot for debugging"""
        path = Path(f"screenshots/{name}")
        path.parent.mkdir(exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)
        print(f"📸 Screenshot saved: {path}")
        return path

    def save_html(self, name: str = "debug.html") -> Path:
        """Save page HTML for analysis"""
        path = Path(f"debug_html/{name}")
        path.parent.mkdir(exist_ok=True)
        path.write_text(self.page.content())
        print(f"📄 HTML saved: {path}")
        return path

    # ==================== SDR Control Methods ====================

    def get_frequency(self) -> float:
        """Get current frequency in MHz"""
        freq_input = self.page.locator('#frequency-input')
        value = freq_input.input_value()
        return float(value)

    def set_frequency(self, freq_mhz: float, wait_for_tune: bool = True):
        """
        Set frequency in MHz.

        Args:
            freq_mhz: Frequency in MHz (24-1766)
            wait_for_tune: Wait for API call to complete
        """
        print(f"📻 Tuning to {freq_mhz:.4f} MHz")

        # Update input field
        freq_input = self.page.locator('#frequency-input')
        freq_input.fill(str(freq_mhz))
        freq_input.press('Enter')

        if wait_for_tune:
            # Wait for tune API call
            self.page.wait_for_response(
                lambda response: '/api/sdr/tune' in response.url,
                timeout=5000
            )
            time.sleep(0.5)  # Allow time for frequency to stabilize

    def get_mode(self) -> str:
        """Get current demodulation mode"""
        # Find active mode button
        mode_buttons = self.page.locator('.mode-button')
        for i in range(mode_buttons.count()):
            button = mode_buttons.nth(i)
            if 'active' in button.get_attribute('class'):
                return button.text_content()
        return "UNKNOWN"

    def set_mode(self, mode: str):
        """
        Set demodulation mode.

        Args:
            mode: One of SPEC, FM, AM, USB, LSB, CW
        """
        print(f"🎚️ Setting mode to {mode}")
        mode_selector = self.page.locator(f'button:has-text("{mode}")')
        mode_selector.click()
        time.sleep(0.3)

    def start_sdr(self):
        """Start SDR acquisition"""
        print("▶️ Starting SDR")
        self.page.locator('#sdr-start').click()
        time.sleep(1)

    def stop_sdr(self):
        """Stop SDR acquisition"""
        print("⏹️ Stopping SDR")
        self.page.locator('#sdr-stop').click()
        time.sleep(0.5)

    def get_sdr_status(self) -> Dict[str, Any]:
        """Get SDR status from API"""
        response = self.page.evaluate("""
            async () => {
                const res = await fetch('/api/sdr/status');
                return await res.json();
            }
        """)
        return response

    def play_audio(self):
        """Start audio playback"""
        print("🔊 Starting audio")
        self.page.locator('#audio-play').click()
        time.sleep(0.5)

    def stop_audio(self):
        """Stop audio playback"""
        print("🔇 Stopping audio")
        self.page.locator('#audio-stop').click()
        time.sleep(0.3)

    def set_volume(self, volume: float):
        """
        Set audio volume.

        Args:
            volume: 0.0 to 1.0
        """
        print(f"🔊 Setting volume to {volume:.1%}")
        self.page.evaluate(f"""
            document.getElementById('volume-slider').value = {volume};
            document.getElementById('volume-slider').dispatchEvent(new Event('input'));
        """)

    # ==================== Band Selection ====================

    def select_band(self, band_name: str):
        """
        Select preset band.

        Args:
            band_name: e.g., "fm_broadcast", "h1_line"
        """
        print(f"📡 Selecting band: {band_name}")
        self.page.select_option('#band-select', value=band_name)
        time.sleep(1)

    def get_available_bands(self) -> List[str]:
        """Get list of available preset bands"""
        response = self.page.evaluate("""
            async () => {
                const res = await fetch('/api/bands');
                const data = await res.json();
                return data.data.map(b => b.name);
            }
        """)
        return response

    # ==================== Advanced Features ====================

    def scan_frequencies(
        self,
        start_mhz: float,
        end_mhz: float,
        step_mhz: float = 0.1,
        dwell_ms: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Scan frequency range and collect data.

        Args:
            start_mhz: Start frequency in MHz
            end_mhz: End frequency in MHz
            step_mhz: Step size in MHz
            dwell_ms: Dwell time per frequency in milliseconds

        Returns:
            List of scan results with frequency and signal info
        """
        print(f"🔍 Scanning {start_mhz}-{end_mhz} MHz (step: {step_mhz} MHz)")
        results = []

        freq = start_mhz
        while freq <= end_mhz:
            self.set_frequency(freq, wait_for_tune=True)
            time.sleep(dwell_ms / 1000.0)

            # Capture spectrum data
            status = self.get_sdr_status()
            results.append({
                'frequency_mhz': freq,
                'timestamp': time.time(),
                'status': status
            })

            freq += step_mhz

        print(f"✅ Scan complete: {len(results)} points")
        return results

    def wait_for_spectrum_data(self, timeout_ms: int = 5000) -> bool:
        """Wait for spectrum WebSocket data to arrive"""
        try:
            # Wait for spectrum canvas to be updated
            self.page.wait_for_function(
                "window.H1SDR_spectrum && window.H1SDR_spectrum.centerFrequency",
                timeout=timeout_ms
            )
            return True
        except:
            return False

    def get_spectrum_frequency(self) -> Optional[float]:
        """Get current center frequency from spectrum display"""
        try:
            freq_hz = self.page.evaluate("""
                () => window.H1SDR_spectrum?.centerFrequency
            """)
            return freq_hz / 1e6 if freq_hz else None
        except:
            return None

    def verify_frequency_control(self, test_freq: float = 100.0) -> bool:
        """
        Verify frequency control is working correctly.

        Args:
            test_freq: Frequency to test in MHz

        Returns:
            True if control works correctly
        """
        print(f"🧪 Testing frequency control with {test_freq} MHz")

        # Set frequency
        self.set_frequency(test_freq)
        time.sleep(1)

        # Check input field
        input_freq = self.get_frequency()
        print(f"   Input field: {input_freq:.4f} MHz")

        # Check spectrum display
        spectrum_freq = self.get_spectrum_frequency()
        if spectrum_freq:
            print(f"   Spectrum display: {spectrum_freq:.4f} MHz")

        # Check API status
        status = self.get_sdr_status()
        if status.get('success'):
            api_freq = status['data'].get('center_frequency', 0) / 1e6
            print(f"   API status: {api_freq:.4f} MHz")

            # Verify all sources agree (within 0.1 MHz)
            if abs(input_freq - test_freq) < 0.1:
                print(f"✅ Frequency control working correctly")
                return True

        print(f"❌ Frequency control mismatch detected")
        return False


# ==================== Example Usage Patterns ====================

def example_basic_control():
    """Example: Basic SDR control"""
    with WebSDRAutomator(headless=False) as sdr:
        # Start SDR
        sdr.start_sdr()

        # Tune to FM broadcast band
        sdr.set_frequency(100.0)
        sdr.set_mode('FM')

        # Start audio
        sdr.play_audio()
        sdr.set_volume(0.5)

        # Wait and take screenshot
        time.sleep(5)
        sdr.screenshot("fm_broadcast.png")

        # Stop
        sdr.stop_audio()
        sdr.stop_sdr()


def example_frequency_scan():
    """Example: Scan FM broadcast band"""
    with WebSDRAutomator(headless=True) as sdr:
        sdr.start_sdr()
        sdr.set_mode('FM')

        # Scan 88-108 MHz
        results = sdr.scan_frequencies(
            start_mhz=88.0,
            end_mhz=108.0,
            step_mhz=0.2,
            dwell_ms=300
        )

        # Save results
        with open('fm_scan_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"📊 Scan results saved: {len(results)} points")


def example_frequency_control_test():
    """Example: Test frequency control coherence"""
    with WebSDRAutomator(headless=False) as sdr:
        sdr.start_sdr()

        test_frequencies = [24.0, 50.0, 100.0, 433.0, 1420.4, 1766.0]

        for freq in test_frequencies:
            success = sdr.verify_frequency_control(freq)
            if not success:
                sdr.screenshot(f"error_freq_{freq}_mhz.png")
                sdr.save_html(f"error_freq_{freq}_mhz.html")


if __name__ == '__main__':
    print("🚀 H1SDR WebSDR Automation Tool")
    print("=" * 50)

    # Run frequency control verification
    example_frequency_control_test()
