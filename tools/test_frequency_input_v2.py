#!/usr/bin/env python3
"""Test frequency input behavior with cache bypass"""

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

        # Hard refresh to bypass cache
        print("🔄 Hard refresh (Ctrl+Shift+R)...")
        await page.reload(wait_until='networkidle')
        await asyncio.sleep(1)

        # Wait for frequency input to be visible
        freq_input = page.locator('#frequency-input')
        await freq_input.wait_for()

        print("\n✅ Frequency input found!")
        print(f"   Initial value: {await freq_input.input_value()}")

        # Test Enter key with typed value
        print("\n🧪 MAIN TEST: Type '88.5' and press Enter...")
        await freq_input.click()
        await freq_input.fill('')  # Clear
        await freq_input.type('88.5', delay=50)
        print(f"   After typing (before Enter): {await freq_input.input_value()}")

        await freq_input.press('Enter')
        await asyncio.sleep(0.5)

        final_value = await freq_input.input_value()
        print(f"   After pressing Enter: {final_value}")

        if final_value == "88.5000":
            print("   ✅ PASS: Enter key works correctly!")
        else:
            print(f"   ❌ FAIL: Expected 88.5000, got {final_value}")

        # Keep browser open
        print("\n⏸️  Browser open for inspection. Close to exit.")
        await asyncio.sleep(3600)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(test_frequency_input())
