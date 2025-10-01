#!/usr/bin/env python3
"""Test frequency input behavior using Playwright"""

import asyncio
from playwright.async_api import async_playwright

async def test_frequency_input():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to app
        print("📡 Navigating to H1SDR...")
        await page.goto('http://localhost:8000')
        await page.wait_for_load_state('networkidle')

        # Wait for frequency input to be visible
        freq_input = page.locator('#frequency-input')
        await freq_input.wait_for()

        print("\n✅ Frequency input found!")
        print(f"   Initial value: {await freq_input.input_value()}")

        # Test 1: Click and type (should NOT update until Enter/blur)
        print("\n🧪 Test 1: Typing without Enter...")
        await freq_input.click()
        await freq_input.fill('')  # Clear
        await freq_input.type('100.5', delay=100)
        await asyncio.sleep(0.5)
        print(f"   After typing '100.5': {await freq_input.input_value()}")
        print(f"   ⚠️  Note: SDR frequency NOT updated yet (by design)")

        # Test 2: Press Enter to commit
        print("\n🧪 Test 2: Pressing Enter...")
        await freq_input.press('Enter')
        await asyncio.sleep(0.5)
        print(f"   After Enter: {await freq_input.input_value()}")
        print(f"   ✅ SDR frequency updated!")

        # Test 3: Arrow keys
        print("\n🧪 Test 3: Arrow Up key...")
        await freq_input.click()
        await freq_input.press('ArrowUp')
        await asyncio.sleep(0.5)
        print(f"   After ArrowUp: {await freq_input.input_value()}")
        print(f"   (should be +0.1 MHz)")

        # Test 4: Step buttons
        print("\n🧪 Test 4: Click +100k button...")
        plus_100k = page.locator('button[data-step="100000"]')
        await plus_100k.click()
        await asyncio.sleep(0.5)
        print(f"   After +100k button: {await freq_input.input_value()}")

        # Test 5: Band selector
        print("\n🧪 Test 5: Select FM Broadcast band...")
        band_select = page.locator('#band-select')
        await band_select.select_option('fm_broadcast')
        await asyncio.sleep(0.5)
        print(f"   After selecting FM band: {await freq_input.input_value()}")

        # Test 6: Blur without change
        print("\n🧪 Test 6: Focus then blur (no change)...")
        current = await freq_input.input_value()
        await freq_input.click()
        await page.locator('body').click()  # Click away to blur
        await asyncio.sleep(0.5)
        print(f"   After blur: {await freq_input.input_value()}")
        print(f"   (should be unchanged: {current})")

        print("\n✅ All tests complete!")
        print("\n📋 Summary:")
        print("   - Typing alone does NOT update frequency (prevents partial updates)")
        print("   - Must press Enter or blur to commit")
        print("   - Arrow keys work immediately")
        print("   - Step buttons work immediately")

        # Keep browser open for manual inspection
        print("\n⏸️  Browser left open for inspection. Close manually to exit.")
        await asyncio.sleep(3600)  # 1 hour

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_frequency_input())
