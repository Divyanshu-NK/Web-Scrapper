from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from datetime import date

from .database import DatabaseManager
from .scrapers.orchestrator import ScraperOrchestrator

app = FastAPI(
    title="Kurti Trend Intelligence API",
    description="Backend API for scraping, tracking, and scoring Kurti design trends.",
    version="3.1"
)

# Enable CORS for frontend dashboard queries
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Database and Orchestrator
db = DatabaseManager()
orchestrator = ScraperOrchestrator(db)

@app.get("/")
def read_root():
    return {
        "app": "Kurti Trend Intelligence Platform API",
        "status": "active",
        "version": "3.1"
    }

@app.get("/api/products")
def get_products(
    limit: int = Query(32, description="Limit results"),
    min_rating: float = Query(0.0, description="Minimum rating"),
    min_reviews: int = Query(0, description="Minimum reviews count"),
    price_min: float = Query(0.0, description="Minimum price filter"),
    price_max: float = Query(99999.0, description="Maximum price filter"),
    platforms: Optional[List[str]] = Query(None, description="Filter by platforms"),
    keyword: Optional[str] = Query("kurti", description="Keyword to filter product titles")
):
    """Retrieves trending products sorted by overall trend scores, with optional keyword filter"""
    try:
        plats = [p.lower() for p in platforms] if platforms else None

        products = db.get_trending_products(
            limit=limit,
            min_rating=min_rating,
            min_reviews=min_reviews,
            price_min=price_min,
            price_max=price_max,
            platforms=plats,
            keyword=keyword
        )
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/all")
def get_all_products(
    limit: int = 200,
    keyword: Optional[str] = Query(None, description="Keyword to filter product titles")
):
    """Retrieves catalog product lists sorted by created date"""
    try:
        products = db.get_all_products(limit=limit, keyword=keyword)
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/all-time-demand")
def get_all_time_demand(
    limit: int = Query(50, description="Number of top products to return"),
    keyword: Optional[str] = Query("kurti", description="Keyword to filter")
):
    """Returns top all-time demand products ranked by total lifetime review count and trend score"""
    try:
        return db.get_all_time_demand_products(limit=limit, keyword=keyword)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
def get_product_details(product_id: str):
    """Retrieves single product and its metrics history for charts"""
    try:
        sql_product = "SELECT * FROM products WHERE id = %s"
        prod_rows = db.execute_query(sql_product, (product_id,))
        if not prod_rows:
            raise HTTPException(status_code=404, detail="Product not found")

        product = prod_rows[0]
        if not db.is_postgres and isinstance(product.get('attributes'), str):
            product['attributes'] = db.deserialize_json(product['attributes'])

        # Get 90-day history
        history = db.get_product_metrics_history(product_id, limit=90)

        # Get latest score details
        sql_score = "SELECT * FROM trend_scores WHERE product_id = %s ORDER BY calculated_date DESC LIMIT 1"
        score_rows = db.execute_query(sql_score, (product_id,))
        latest_score = score_rows[0] if score_rows else {}

        return {
            "product": product,
            "score": latest_score,
            "metrics_history": history
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/attributes")
def get_attribute_analytics(limit: int = 100):
    """Retrieves monthly attribute trend rankings"""
    try:
        return db.get_attribute_trends(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scraper/scrape")
def trigger_scrape(
    background_tasks: BackgroundTasks,
    platforms: List[str] = Query(..., description="List of platforms to scrape"),
    keyword: str = Query("kurti", description="Keyword to search for")
):
    """Triggers real live scraper in the background. 
    Requires Apify API key, Playwright, or Selenium+ChromeDriver to be configured."""
    try:
        if not platforms:
            raise HTTPException(status_code=400, detail="Must select at least one platform to scrape.")

        background_tasks.add_task(
            orchestrator.run_orchestrator,
            platforms=platforms,
            keyword=keyword
        )

        return {
            "status": "accepted",
            "message": "Live scrape task initiated in background. Check status using scraper jobs list.",
            "platforms": platforms,
            "keyword": keyword
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scraper/jobs")
def get_scraper_jobs(limit: int = 10):
    """Retrieves recent job executions history logs"""
    try:
        return db.get_scrape_jobs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/saved-products")
def get_saved_products():
    """Retrieves all bookmarked/saved products"""
    try:
        return db.get_saved_products()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/saved-products/{product_id}")
def save_product(product_id: str):
    """Saves a product to bookmarks"""
    try:
        success = db.bookmark_product(product_id)
        return {"status": "saved", "product_id": product_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/saved-products/{product_id}")
def delete_saved_product(product_id: str):
    """Removes a product from bookmarks"""
    try:
        success = db.remove_saved_product(product_id)
        return {"status": "removed", "product_id": product_id, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sources")
def get_sources():
    """Retrieves all available built-in and user-added brand sources"""
    try:
        from .scrapers.brand_scraper import BRAND_CONFIGS
        builtin_names = [cfg["name"] for cfg in BRAND_CONFIGS.values()]
        builtin_names.extend(["Myntra", "Flipkart"])
        
        custom = db.get_custom_sources()
        custom_list = [{"brand_key": c["brand_key"], "name": c["name"], "url": c["url"], "is_custom": True} for c in custom]
        
        return {
            "builtin": sorted(list(set(builtin_names))),
            "custom": custom_list,
            "all_names": sorted(list(set(builtin_names + [c["name"] for c in custom])))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CustomSourcePayload(dict):
    pass

@app.post("/api/sources")
def add_custom_source(
    name: str = Query(..., description="Brand or store name"),
    url: str = Query(..., description="Website or collection feed URL")
):
    """Registers a new custom website / brand to scan for products"""
    try:
        if not name or not url:
            raise HTTPException(status_code=400, detail="Name and URL are required.")

        raw_url = url.strip()
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = f"https://{raw_url}"

        clean_name = name.strip()
        brand_key = clean_name.lower().replace(" ", "").replace("_", "").replace("-", "")

        # Format Shopify / D2C feed URLs
        parsed_domain = raw_url.split("//")[-1].split("/")[0]
        base_domain = f"https://{parsed_domain}"

        if raw_url.endswith(".json"):
            feed_url = raw_url
            fallback_url = f"{base_domain}/products.json?limit=50"
        elif "/collections/" in raw_url:
            clean_path = raw_url.rstrip("/")
            feed_url = f"{clean_path}/products.json?limit=50" if not clean_path.endswith(".json") else clean_path
            fallback_url = f"{base_domain}/products.json?limit=50"
        else:
            feed_url = f"{base_domain}/products.json?limit=50"
            fallback_url = f"{base_domain}/collections/all/products.json?limit=50"

        base_product_url = f"{base_domain}/products/"

        db.add_custom_source(
            brand_key=brand_key,
            name=clean_name,
            url=feed_url,
            fallback_url=fallback_url,
            base_url=base_product_url
        )

        return {
            "status": "success",
            "message": f"Successfully registered custom source '{clean_name}'.",
            "brand_key": brand_key,
            "name": clean_name,
            "feed_url": feed_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sources/{brand_key}")
def delete_source(brand_key: str):
    """Deletes a custom website source"""
    try:
        db.delete_custom_source(brand_key)
        return {"status": "success", "message": f"Source {brand_key} removed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


