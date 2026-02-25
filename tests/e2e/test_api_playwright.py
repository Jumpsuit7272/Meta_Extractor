"""E2E tests using Playwright for API verification.
   Run with server: python -m uvicorn rpd.main:app --port 8000
   Then: pytest tests/e2e -v --base-url=http://localhost:8000
"""

import pytest
import httpx
from playwright.async_api import async_playwright


@pytest.fixture(scope="session")
def base_url():
    return "http://localhost:8000"


def _ui_available(base_url: str) -> bool:
    """Check if UI is served at /static/index.html."""
    try:
        r = httpx.get(f"{base_url}/static/index.html", timeout=2)
        return r.status_code == 200 and "uploadZone" in r.text
    except Exception:
        return False


@pytest.mark.asyncio
async def test_root_page_loads(base_url):
    """Root redirects to UI; page loads with RPD content."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(base_url, wait_until="load")
        content = await page.content()
        assert "RPD" in content or "rpd" in content.lower()
        await browser.close()


@pytest.mark.asyncio
async def test_health_check(base_url):
    """Health endpoint returns ok."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        resp = await page.goto(f"{base_url}/health")
        assert resp and resp.ok
        data = await page.evaluate("() => fetch('/health').then(r => r.json())")
        assert data.get("status") == "ok"
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not _ui_available("http://localhost:8000"), reason="UI not available (start server with: uvicorn rpd.main:app --port 8000)")
async def test_ui_extract_tab(base_url):
    """UI loads with Extract tab content (via /static/index.html)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        resp = await page.goto(f"{base_url}/static/index.html", wait_until="load")
        assert resp and resp.ok
        content = await page.content()
        assert "uploadZone" in content or "Extract metadata" in content or "Drop a file" in content
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not _ui_available("http://localhost:8000"), reason="UI not available (start server with: uvicorn rpd.main:app --port 8000)")
async def test_ui_bulk_tab(base_url):
    """UI has Bulk tab with multi-file upload zone."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        resp = await page.goto(f"{base_url}/static/index.html", wait_until="load")
        assert resp and resp.ok
        content = await page.content()
        assert "Bulk" in content and ("bulkUploadZone" in content or "Bulk upload" in content or "multiple files" in content)
        await page.click('button[data-tab="bulk"]')
        await page.wait_for_selector("#bulkUploadZone, #bulkFileInput", timeout=3000)
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not _ui_available("http://localhost:8000"), reason="UI not available (start server with: uvicorn rpd.main:app --port 8000)")
async def test_ui_theme_toggle(base_url):
    """Theme toggle (Light/Dark) exists and is clickable."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        resp = await page.goto(f"{base_url}/static/index.html", wait_until="load")
        assert resp and resp.ok
        content = await page.content()
        assert "themeFloat" in content or "themeLight" in content, f"Theme toggle not in page. Has Bulk: {'Bulk' in content}, has themeFloat: {'themeFloat' in content}"
        await page.wait_for_selector("#themeLight, .theme-btn", timeout=3000)
        await page.click("#themeLight", timeout=5000)
        assert await page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light"
        await page.click("#themeDark", timeout=5000)
        assert await page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark"
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not _ui_available("http://localhost:8000"), reason="UI not available (start server with: uvicorn rpd.main:app --port 8000)")
async def test_ui_compare_tab(base_url):
    """UI has Compare tab and Document A/B inputs."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        resp = await page.goto(f"{base_url}/static/index.html", wait_until="load")
        assert resp and resp.ok
        content = await page.content()
        assert "Compare" in content and ("Document A" in content or "compare" in content.lower())
        await browser.close()


@pytest.mark.asyncio
async def test_openapi_docs(base_url):
    """OpenAPI docs page loads."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"{base_url}/docs")
        await page.wait_for_selector("text=OpenAPI", timeout=5000)
        assert "/extract" in await page.content()
        await browser.close()
