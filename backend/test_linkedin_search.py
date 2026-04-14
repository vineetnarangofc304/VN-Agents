"""
LinkedIn Search POC - v2 with country code fix
"""
import asyncio
import json
from playwright.async_api import async_playwright

LINKEDIN_EMAIL = "+919667820236"
LINKEDIN_PASS = "HearClear@2025"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Step 1: Login
        print("=== Step 1: Navigating to LinkedIn login ===")
        await page.goto("https://www.linkedin.com/login", wait_until="networkidle", timeout=30000)
        
        # Fill credentials with country code
        await page.fill('#username', LINKEDIN_EMAIL)
        await page.fill('#password', LINKEDIN_PASS)
        await page.screenshot(path="/app/backend/uploads/li_v2_before_submit.png")
        
        await page.click('button[type="submit"]')
        print("=== Clicked submit, waiting... ===")
        
        # Wait for navigation
        try:
            await page.wait_for_url("**/feed**", timeout=15000)
            print("=== Redirected to feed - LOGIN SUCCESS ===")
        except:
            await page.wait_for_timeout(5000)
            print(f"After login URL: {page.url}")
        
        await page.screenshot(path="/app/backend/uploads/li_v2_after_login.png")
        current_url = page.url
        print(f"Current URL: {current_url}")
        
        # Check for challenges
        if "checkpoint" in current_url or "challenge" in current_url:
            print("!!! SECURITY CHALLENGE !!!")
            # Get the page content to understand what's asked
            text_content = await page.evaluate("() => document.body.innerText")
            print(f"Page text: {text_content[:1000]}")
            await browser.close()
            return
        
        # Step 2: Navigate to search
        search_query = "looking for agency"
        encoded = search_query.replace(' ', '%20')
        search_url = f"https://www.linkedin.com/search/results/content/?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER"
        
        print(f"\n=== Step 2: Searching '{search_query}' ===")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/app/backend/uploads/li_v2_search.png")
        print(f"Search URL: {page.url}")
        
        # Get page text
        text_content = await page.evaluate("() => document.body.innerText")
        print(f"\nPage text (first 2000 chars):\n{text_content[:2000]}")
        
        # Scroll to load more
        for i in range(3):
            await page.evaluate("window.scrollBy(0, 1500)")
            await page.wait_for_timeout(2000)
        
        await page.screenshot(path="/app/backend/uploads/li_v2_search_scrolled.png")
        
        # Extract structured post data
        posts_data = await page.evaluate("""
            () => {
                const posts = [];
                // Try various LinkedIn selectors for search result posts
                const containers = document.querySelectorAll(
                    '.feed-shared-update-v2, ' +
                    '[data-chameleon-result-urn], ' +
                    '.reusable-search__result-container, ' +
                    '.search-content__result'
                );
                
                containers.forEach((el, idx) => {
                    const text = el.innerText || '';
                    const links = Array.from(el.querySelectorAll('a[href*="/posts/"], a[href*="/feed/update/"]'));
                    const postLink = links.length > 0 ? links[0].href : '';
                    
                    posts.push({
                        index: idx,
                        text_preview: text.substring(0, 500),
                        post_link: postLink
                    });
                });
                
                return {
                    total: containers.length,
                    posts: posts.slice(0, 20)
                };
            }
        """)
        
        print(f"\n=== Found {posts_data['total']} post containers ===")
        for p_data in posts_data.get('posts', []):
            print(f"\n--- Post {p_data['index']} ---")
            print(f"Link: {p_data['post_link']}")
            print(f"Preview: {p_data['text_preview'][:200]}")
        
        with open("/app/backend/uploads/li_v2_results.json", "w") as f:
            json.dump(posts_data, f, indent=2)
        
        await browser.close()
        print("\n=== DONE ===")

if __name__ == "__main__":
    asyncio.run(main())
