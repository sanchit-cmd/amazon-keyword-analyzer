import asyncio
from typing import Dict, List, Optional, TypedDict
from playwright.async_api import async_playwright
from google.adk.agents.llm_agent import Agent


# Define Structures
class ProductData(TypedDict):
    url: str
    title: str
    description: str
    brand: Optional[str]
    price: str
    specifications: Dict[str, str]
    about_product: List[str]


# High-Speed Scraper Tool Function with Interstitial Handler
async def get_amazon_product_data(link: str) -> Optional[ProductData]:
    """
    Highly optimized async scraper for Amazon product pages.
    Handles interstitial 'Continue shopping' screens gracefully.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Route Interception for Speed (Aborting styles/images)
        async def block_heavy_assets(route):
            if route.request.resource_type in [
                "image",
                "stylesheet",
                "font",
                "media",
                "ping",
            ]:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", block_heavy_assets)

        try:
            await page.goto(link, wait_until="domcontentloaded", timeout=15000)

            # --- INTERSTITIAL CHECK LAYER ---
            # Locate the exact button by its type/text combination safely
            continue_button = page.locator(
                'button[type="submit"]:has-text("Continue shopping")'
            )

            # Check if this gatekeeping screen is visible
            if await continue_button.is_visible():
                print("Detected 'Continue shopping' gate. Clicking through...")
                await continue_button.click()
                # Give the structural page a tiny moment to switch contexts
                await page.wait_for_timeout(1500)

            # Wait for the true product title layout to structuralize
            await page.locator("#title").wait_for(state="attached", timeout=5000)

            # Extract Primary Fields
            title = (await page.locator("#title").inner_text()).strip()

            raw_brand = await page.locator("#bylineInfo").inner_text()
            brand = (
                raw_brand.split(":")[1].strip()
                if ":" in raw_brand
                else raw_brand.strip()
            )

            price_loc = page.locator("#corePrice_feature_div .a-price-whole")
            price = (
                (await price_loc.inner_text()).strip()
                if await price_loc.count() > 0
                else "N/A"
            )

            desc_loc = page.locator("#productDescription span")
            description = (
                (await desc_loc.inner_html()).strip()
                if await desc_loc.count() > 0
                else "N/A"
            )

            # Parse Specifications Table
            table_rows = await page.locator('tr[role="listitem"]').all()
            specifications = {}
            for row in table_rows:
                key_loc = row.locator(".a-text-bold")
                val_loc = row.locator(".po-break-word")
                if await key_loc.count() > 0 and await val_loc.count() > 0:
                    key = (await key_loc.inner_html()).strip()
                    val = (await val_loc.inner_html()).strip()
                    specifications[key] = val

            # Parse Bullet Points
            about_point = []
            about_section = page.locator("#feature-bullets")
            about_list_items = await about_section.locator("li").all()
            for item in about_list_items:
                span_loc = item.locator("span")
                if await span_loc.count() > 0:
                    point = (await span_loc.inner_html()).strip()
                    about_point.append(point)

            return {
                "about_product": about_point,
                "brand": brand,
                "description": description,
                "price": price,
                "specifications": specifications,
                "title": title,
                "url": link,
            }
        except Exception as e:
            return {"error": f"Scraping failed or timed out: {str(e)}"}
        finally:
            await context.close()
            await browser.close()


# Register the Agent Module for ADK Web execution
root_agent = Agent(
    model="gemini-2.5-flash",
    name="amazon_keyword_agent",
    description="Extracts SEO ranking keywords from any Amazon link.",
    instruction="""
    You are an expert Amazon SEO agent. When a user gives you a link, you must:
    1. Call the `get_amazon_product_data` tool using the exact link provided.
    2. Read the structured product details returned by the tool.
    3. Determine the best, highest-impact keywords that would make this product rank higher on Amazon search.
    4. Provide the result strictly matching the expected output schema layout.
    """,
    tools=[get_amazon_product_data],
)
