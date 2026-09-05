import os
import time
import requests
import logging
from typing import List, Dict, Any, Optional
from ..config import settings

logger = logging.getLogger(__name__)

class ApifyScraper:
    """Production scraper connector using Apify API endpoints"""
    
    def __init__(self):
        self.api_token = settings.APIFY_API_TOKEN
        self.base_url = 'https://api.apify.com/v2'
        
    def _is_configured(self) -> bool:
        return bool(self.api_token)

    def run_scraper(self, actor_id: str, input_data: Dict[str, Any]) -> str:
        """Starts a scraper run and returns run_id"""
        if not self._is_configured():
            raise ValueError("APIFY_API_TOKEN is not configured in environment settings.")
            
        url = f"{self.base_url}/acts/{actor_id}/runs"
        headers = {'Authorization': f'Bearer {self.api_token}'}
        
        response = requests.post(url, json=input_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()['data']['id']
    
    def get_results(self, actor_id: str, run_id: str, timeout_seconds: int = 300) -> List[Dict[str, Any]]:
        """Polls for scraper run success and returns dataset items"""
        if not self._is_configured():
            raise ValueError("APIFY_API_TOKEN is not configured in environment settings.")
            
        url = f"{self.base_url}/acts/{actor_id}/runs/{run_id}"
        headers = {'Authorization': f'Bearer {self.api_token}'}
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            status = data['data']['status']
            if status == 'SUCCEEDED':
                # Fetch dataset items
                dataset_id = data['data']['defaultDatasetId']
                dataset_url = f"{self.base_url}/datasets/{dataset_id}/items"
                dataset_response = requests.get(dataset_url, headers=headers, timeout=30)
                dataset_response.raise_for_status()
                return dataset_response.json()
            elif status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                raise RuntimeError(f"Scraper run failed with status: {status}")
                
            time.sleep(10)
            
        raise TimeoutError(f"Scraper {actor_id} run {run_id} timed out")
    
    def scrape_myntra(self, keyword: str = 'kurti', max_items: int = 20) -> List[Dict[str, Any]]:
        """Scrapes Myntra using official actor oUpJN7QaTKBwYqKQe"""
        if not self._is_configured():
            logger.warning("Apify API Token not configured. Cannot perform real Myntra scrape.")
            return []
            
        actor_id = 'oUpJN7QaTKBwYqKQe'
        input_data = {
            'keyword': keyword,
            'maxItems': max_items,
            'countryCode': 'IN',
            'includeReviews': True
        }
        
        try:
            logger.info("Triggering Apify Myntra scraper run...")
            run_id = self.run_scraper(actor_id, input_data)
            items = self.get_results(actor_id, run_id)
            
            # Format to standardize product layout
            formatted = []
            for item in items:
                formatted.append({
                    "platform": "myntra",
                    "platform_product_id": str(item.get('id', '')),
                    "product_url": item.get('url', ''),
                    "title": item.get('title', ''),
                    "brand": item.get('brand', 'Unknown'),
                    "price": float(item.get('price', 0.0) or 0.0),
                    "original_price": float(item.get('originalPrice', item.get('price', 0.0)) or 0.0),
                    "discount_percentage": float(item.get('discountPercent', 0.0) or 0.0),
                    "rating": float(item.get('rating', 0.0) or 0.0),
                    "review_count": int(item.get('reviewsCount', 0) or 0),
                    "image_url": item.get('imageUrl', ''),
                    "description": item.get('description', ''),
                    "attributes": {
                        "neckline": item.get('neck', 'Round'),
                        "fabric": item.get('fabric', 'Cotton'),
                        "pattern": item.get('pattern', 'Solid')
                    },
                    "launch_date": item.get('launchDate', date.today().isoformat()),
                    "launch_source": "badge"
                })
            return formatted
        except Exception as e:
            logger.error(f"Apify Myntra scraper run failed: {e}")
            return []
    
    def scrape_flipkart(self, keyword: str = 'kurti', max_items: int = 20) -> List[Dict[str, Any]]:
        """Scrapes Flipkart using official actor EmCMtdx8bLwGfjDPj"""
        if not self._is_configured():
            logger.warning("Apify API Token not configured. Cannot perform real Flipkart scrape.")
            return []
            
        actor_id = 'EmCMtdx8bLwGfjDPj'
        input_data = {
            'keyword': keyword,
            'maxItems': max_items,
            'countryCode': 'IN'
        }
        
        try:
            logger.info("Triggering Apify Flipkart scraper run...")
            run_id = self.run_scraper(actor_id, input_data)
            items = self.get_results(actor_id, run_id)
            
            # Format to standardize product layout
            formatted = []
            for item in items:
                formatted.append({
                    "platform": "flipkart",
                    "platform_product_id": str(item.get('id', '')),
                    "product_url": item.get('url', ''),
                    "title": item.get('title', ''),
                    "brand": item.get('brand', 'Unknown'),
                    "price": float(item.get('price', 0.0) or 0.0),
                    "original_price": float(item.get('originalPrice', item.get('price', 0.0)) or 0.0),
                    "discount_percentage": float(item.get('discountPercent', 0.0) or 0.0),
                    "rating": float(item.get('rating', 0.0) or 0.0),
                    "review_count": int(item.get('reviewsCount', 0) or 0),
                    "image_url": item.get('imageUrl', ''),
                    "description": item.get('description', ''),
                    "attributes": {
                        "neckline": item.get('neck', 'Round'),
                        "fabric": item.get('fabric', 'Cotton'),
                        "pattern": item.get('pattern', 'Solid')
                    },
                    "launch_date": date.today().isoformat(),
                    "launch_source": "estimated"
                })
            return formatted
        except Exception as e:
            logger.error(f"Apify Flipkart scraper run failed: {e}")
            return []
