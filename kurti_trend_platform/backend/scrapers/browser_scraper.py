import re
import random
import time
import asyncio
import logging
import uuid
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Fallback structures in case selenium/playwright are not installed
SELENIUM_AVAILABLE = False
PLAYWRIGHT_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    pass

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

class BrowserScraper:
    """Browser-based scraping using Selenium (Meesho) and Playwright (Myntra)"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
    
    def _get_chrome_options(self) -> Any:
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f'user-agent={random.choice(self.user_agents)}')
        return options

    def scrape_meesho(self, max_items: int = 20) -> List[Dict[str, Any]]:
        """Scrapes Meesho Kurtis using Selenium"""
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium is not installed or available. Skipping Meesho scrape.")
            return []
            
        logger.info("Starting Selenium scraper for Meesho ethnic kurtis...")
        options = self._get_chrome_options()
        
        # Initialize Chrome Service and Driver
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.error(f"Failed to start Selenium WebDriver: {e}")
            return []
            
        try:
            # Hide automation flags
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            
            driver.get('https://www.meesho.com/ethnic-wear/kurtis/')
            time.sleep(4)
            
            products = []
            scroll_attempts = 0
            
            # Loop scrolling to capture enough products
            while len(products) < max_items and scroll_attempts < 5:
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(2.0, 3.5))
                
                # Fetch page items
                data = driver.execute_script('''
                    return Array.from(document.querySelectorAll('[data-testid="product-card"]')).map(card => {
                        return {
                            title: card.querySelector('[data-testid="product-title"]')?.innerText || '',
                            price: card.querySelector('[data-testid="product-price"]')?.innerText || '',
                            rating: card.querySelector('[data-testid="product-rating"]')?.innerText || '',
                            reviews: card.querySelector('[data-testid="product-reviews"]')?.innerText || '',
                            image: card.querySelector('img')?.src || '',
                            url: card.querySelector('a')?.href || ''
                        };
                    });
                ''')
                
                # Merge unique URLs
                for item in data:
                    if item.get('url') and item['url'] not in [p.get('url') for p in products]:
                        products.append(item)
                        
                scroll_attempts += 1
                
            return self._clean_meesho_products(products[:max_items])
            
        except Exception as e:
            logger.error(f"Error during Meesho scrape: {e}")
            return []
        finally:
            driver.quit()

    def _clean_meesho_products(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for item in raw_data:
            if not item.get('title'):
                continue
                
            # Parse price (e.g. "₹299" -> 299.0)
            price_val = 0.0
            try:
                price_str = re.sub(r'[₹,]', '', item.get('price', '0')).strip()
                price_val = float(price_str) if price_str else 0.0
            except ValueError:
                pass
                
            # Parse rating (e.g. "4.1 ★" -> 4.1)
            rating_val = 0.0
            try:
                rating_str = item.get('rating', '0').replace('★', '').strip()
                rating_val = float(rating_str) if rating_str else 0.0
            except ValueError:
                pass
                
            # Parse reviews (e.g. "122 Reviews" -> 122)
            reviews_val = 0
            try:
                rev_str = re.sub(r'[^0-9]', '', item.get('reviews', '0')).strip()
                reviews_val = int(rev_str) if rev_str else 0
            except ValueError:
                pass
                
            cleaned.append({
                "platform": "meesho",
                "platform_product_id": item['url'].split('/')[-1] if item.get('url') else str(uuid.uuid4())[:8],
                "product_url": item.get('url', ''),
                "title": item['title'].strip(),
                "brand": item['title'].split()[0] if item['title'] else "Unknown",
                "price": price_val,
                "original_price": price_val * 1.3,  # estimate discount for meesho
                "discount_percentage": 23.0,
                "rating": rating_val,
                "review_count": reviews_val,
                "image_url": item.get('image', ''),
                "description": f"Beautiful Meesho Kurti: {item['title']}",
                "attributes": {
                    "neckline": "Round", # fallback
                    "fabric": "Rayon",
                    "pattern": "Solid"
                },
                "launch_date": date.today().isoformat(),
                "launch_source": "first_seen"
            })
        return cleaned

    async def scrape_myntra_with_playwright(self, keyword: str = 'kurtis') -> List[Dict[str, Any]]:
        """Scrapes Myntra listings using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright is not installed. Skipping Myntra Playwright scrape.")
            return []
            
        logger.info("Starting Playwright scraper for Myntra...")
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()
                
                await page.goto(f'https://www.myntra.com/{keyword}', timeout=45000)
                await page.wait_for_selector('li.product-base', timeout=20000)
                
                # Scroll a few times
                for _ in range(3):
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(1500)
                    
                # Extract listing contents
                products = await page.evaluate('''
                    () => Array.from(document.querySelectorAll('li.product-base')).map(item => ({
                        title: item.querySelector('h4.product-product')?.innerText || '',
                        brand: item.querySelector('h3.product-brand')?.innerText || '',
                        price: item.querySelector('.product-price span')?.innerText || '',
                        rating: item.querySelector('.product-ratingsContainer')?.innerText || '',
                        image: item.querySelector('img')?.src || '',
                        url: item.querySelector('a')?.href || ''
                    }))
                ''')
                
                await browser.close()
                return self._clean_myntra_products(products)
                
            except Exception as e:
                logger.error(f"Error during Myntra Playwright scrape: {e}")
                return []

    def _clean_myntra_products(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for item in raw_data:
            if not item.get('title'):
                continue
                
            # Parse price (e.g. "Rs. 499" -> 499.0)
            price_val = 0.0
            try:
                price_str = re.sub(r'[^0-9]', '', item.get('price', '0')).strip()
                price_val = float(price_str) if price_str else 0.0
            except ValueError:
                pass
                
            # Parse rating (e.g. "4.2 | 1.2k" -> 4.2)
            rating_val = 0.0
            reviews_val = 0
            rating_raw = item.get('rating', '')
            if rating_raw and '|' in rating_raw:
                parts = rating_raw.split('|')
                try:
                    rating_val = float(parts[0].strip())
                    # Convert 1.2k review count to integer
                    rev_part = parts[1].lower().replace('k', '').strip()
                    rev_multiplier = 1000 if 'k' in parts[1].lower() else 1
                    reviews_val = int(float(rev_part) * rev_multiplier)
                except (ValueError, IndexError):
                    pass
            elif rating_raw:
                try:
                    rating_val = float(rating_raw.strip())
                except ValueError:
                    pass
                    
            cleaned.append({
                "platform": "myntra",
                "platform_product_id": item['url'].split('/')[-2] if item.get('url') else str(uuid.uuid4())[:8],
                "product_url": item.get('url', ''),
                "title": f"{item.get('brand', '')} {item['title']}",
                "brand": item.get('brand', 'Unknown'),
                "price": price_val,
                "original_price": price_val * 1.5,
                "discount_percentage": 33.0,
                "rating": rating_val,
                "review_count": reviews_val,
                "image_url": item.get('image', ''),
                "description": f"Stunning Myntra Kurti by {item.get('brand', '')}",
                "attributes": {
                    "neckline": "Round",
                    "fabric": "Cotton",
                    "pattern": "Solid"
                },
                "launch_date": date.today().isoformat(),
                "launch_source": "first_seen"
            })
            
        return cleaned
