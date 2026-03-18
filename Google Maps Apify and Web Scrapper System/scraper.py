import asyncio
import csv
import re
import time
from dataclasses import dataclass, fields
from pathlib import Path

from playwright.async_api import async_playwright, Page, Locator


@dataclass
class Business:
    name: str = ""
    phone: str = ""
    city: str = ""
    address: str = ""
    website: str = ""
    rating: str = ""
    reviews: str = ""
    category: str = ""


async def slow_scroll(page: Page, container_selector: str, times: int = 10):
    """Scroll the results panel to load more listings."""
    for _ in range(times):
        await page.eval_on_selector(
            container_selector,
            "el => el.scrollBy(0, 800)",
        )
        await asyncio.sleep(1.2)


async def extract_business(page: Page) -> Business:
    """Extract data from the currently open business panel."""
    biz = Business()

    # Name
    try:
        biz.name = await page.locator("h1.DUwDvf").first.inner_text(timeout=3000)
    except Exception:
        pass

    # Category
    try:
        biz.category = await page.locator("button.DkEaL").first.inner_text(timeout=2000)
    except Exception:
        pass

    # Address / City
    try:
        address_el = page.locator('[data-item-id="address"]')
        if await address_el.count() > 0:
            biz.address = await address_el.first.get_attribute("aria-label", timeout=2000) or ""
            biz.address = biz.address.replace("Dirección: ", "").replace("Address: ", "").strip()
            # Extract city from address (last meaningful token before country)
            parts = [p.strip() for p in biz.address.split(",")]
            if len(parts) >= 2:
                biz.city = parts[-2]
    except Exception:
        pass

    # Phone
    try:
        phone_el = page.locator('[data-item-id^="phone:tel:"]')
        if await phone_el.count() > 0:
            label = await phone_el.first.get_attribute("aria-label", timeout=2000) or ""
            biz.phone = re.sub(r"[^\d+\s\-()]", "", label.replace("Teléfono:", "").replace("Phone:", "")).strip()
    except Exception:
        pass

    # Website
    try:
        web_el = page.locator('[data-item-id="authority"]')
        if await web_el.count() > 0:
            biz.website = await web_el.first.get_attribute("href", timeout=2000) or ""
    except Exception:
        pass

    # Rating
    try:
        biz.rating = await page.locator("div.F7nice span[aria-hidden='true']").first.inner_text(timeout=2000)
    except Exception:
        pass

    # Reviews count
    try:
        biz.reviews = await page.locator("div.F7nice span[aria-label]").first.get_attribute("aria-label", timeout=2000) or ""
        biz.reviews = re.sub(r"[^\d,]", "", biz.reviews)
    except Exception:
        pass

    return biz


async def scrape_google_maps(
    queries: list[str],
    output_file: str = "results.csv",
    max_results: int = 100,
    headless: bool = True,
) -> list[Business]:
    all_results: list[Business] = []
    seen_names: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            locale="es-MX",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        context.set_default_timeout(60000)
        page = await context.new_page()

        for query in queries:
            print(f"\n[*] Buscando: {query}")
            encoded = query.replace(" ", "+")
            url = f"https://www.google.com/maps/search/{encoded}"
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(4)

            # Accept cookies if prompted
            try:
                accept_btn = page.locator('button[aria-label*="Aceptar"]').first
                if await accept_btn.count() > 0:
                    await accept_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            results_selector = 'div[role="feed"]'
            try:
                await page.wait_for_selector(results_selector, timeout=10000)
            except Exception:
                print(f"  [!] No se encontró lista de resultados para: {query}")
                continue

            collected = 0
            no_new_count = 0

            while collected < max_results and no_new_count < 5:
                # Get all listing links visible
                listings: list[Locator] = await page.locator(
                    'a[href*="/maps/place/"]'
                ).all()

                new_found = False
                for listing in listings:
                    if collected >= max_results:
                        break

                    href = await listing.get_attribute("href") or ""
                    if href in seen_names:
                        continue

                    seen_names.add(href)
                    new_found = True

                    try:
                        await listing.click()
                        await asyncio.sleep(2.5)

                        biz = await extract_business(page)
                        if biz.name and biz.name not in {b.name for b in all_results}:
                            biz.category = biz.category or query
                            all_results.append(biz)
                            collected += 1
                            print(
                                f"  [{collected:>3}] {biz.name} | "
                                f"{biz.phone or 'sin tel'} | {biz.city or 'sin ciudad'}"
                            )

                        # Go back to results list
                        await page.go_back()
                        await asyncio.sleep(1.5)

                    except Exception as e:
                        print(f"  [!] Error en resultado: {e}")
                        try:
                            await page.go_back()
                            await asyncio.sleep(1)
                        except Exception:
                            pass

                if not new_found:
                    no_new_count += 1
                else:
                    no_new_count = 0

                # Scroll to load more
                try:
                    await slow_scroll(page, results_selector, times=3)
                except Exception:
                    pass

                # Check for "end of results" message
                try:
                    end_msg = await page.locator(
                        'span:has-text("Llegaste al final de la lista")'
                    ).count()
                    if end_msg > 0:
                        print("  [*] Fin de la lista.")
                        break
                except Exception:
                    pass

        await browser.close()

    # Save to CSV
    if all_results:
        save_to_csv(all_results, output_file)
        print(f"\n[+] {len(all_results)} resultados guardados en: {output_file}")
    else:
        print("\n[!] No se encontraron resultados.")

    return all_results


def save_to_csv(businesses: list[Business], output_file: str):
    path = Path(output_file)
    field_names = [f.name for f in fields(Business)]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for biz in businesses:
            writer.writerow(
                {f.name: getattr(biz, f.name) for f in fields(Business)}
            )
