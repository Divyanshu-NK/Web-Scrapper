import os
import uuid
import sqlite3
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from .config import settings

# Attempt to import psycopg2 for Postgres support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

class DatabaseManager:
    """Manages database connection and operations for SQLite/PostgreSQL"""
    
    def __init__(self):
        self.is_postgres = settings.is_postgres
        if self.is_postgres and not POSTGRES_AVAILABLE:
            print("⚠️ PostgreSQL config detected but 'psycopg2' is not installed. Falling back to SQLite.")
            self.is_postgres = False
            
        self.sqlite_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "kurti_trend_intelligence.db"
        )
        self.placeholder = "%s" if self.is_postgres else "?"
        self.init_db()

    def get_connection(self):
        """Returns a connection object and cursor"""
        if self.is_postgres:
            if settings.DATABASE_URL:
                conn = psycopg2.connect(settings.DATABASE_URL)
            else:
                conn = psycopg2.connect(
                    host=settings.DB_HOST,
                    port=settings.DB_PORT or 5432,
                    database=settings.DB_NAME,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD
                )
            # Use DictCursor for PostgreSQL to match dict-like access
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            return conn, cursor
        else:
            conn = sqlite3.connect(self.sqlite_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            return conn, cursor

    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns list of dictionaries"""
        conn, cursor = self.get_connection()
        try:
            # Adapt placeholders for SQLite if needed
            if not self.is_postgres:
                sql = sql.replace("%s", "?")
                
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            if self.is_postgres:
                return [dict(row) for row in rows]
            else:
                return [dict(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    def execute_write(self, sql: str, params: tuple = ()) -> Any:
        """Executes an INSERT/UPDATE/DELETE query and commits"""
        conn, cursor = self.get_connection()
        try:
            if not self.is_postgres:
                sql = sql.replace("%s", "?")
                
            cursor.execute(sql, params)
            conn.commit()
            
            if not self.is_postgres and cursor.lastrowid:
                return cursor.lastrowid
            return None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def init_db(self):
        """Creates database schema and tables if they don't exist"""
        conn, cursor = self.get_connection()
        
        try:
            if self.is_postgres:
                # PostgreSQL + TimescaleDB Setup
                cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
                try:
                    cursor.execute('CREATE EXTENSION IF NOT EXISTS "timescaledb";')
                except Exception:
                    print("⚠️ TimescaleDB extension could not be loaded. Continuing with standard tables.")
                
                # 1. PRODUCTS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        platform VARCHAR(20) NOT NULL,
                        platform_product_id VARCHAR(100),
                        product_url TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        brand VARCHAR(100),
                        price DECIMAL(10,2),
                        original_price DECIMAL(10,2),
                        discount_percentage DECIMAL(5,2),
                        rating DECIMAL(3,2),
                        review_count INTEGER,
                        image_url TEXT,
                        description TEXT,
                        attributes JSONB DEFAULT '{}'::jsonb,
                        launch_date DATE,
                        launch_source VARCHAR(50),
                        first_seen_date DATE NOT NULL,
                        last_seen_date DATE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # 2. DAILY_METRICS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_metrics (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        product_id UUID REFERENCES products(id) ON DELETE CASCADE,
                        date DATE NOT NULL,
                        price DECIMAL(10,2),
                        rating DECIMAL(3,2),
                        review_count INTEGER,
                        is_in_stock BOOLEAN DEFAULT TRUE,
                        rank_on_page INTEGER,
                        daily_review_increment INTEGER DEFAULT 0,
                        estimated_sales_velocity DECIMAL(10,2),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id, date)
                    );
                """)
                
                # Try creating TimescaleDB hypertable
                try:
                    cursor.execute("SELECT create_hypertable('daily_metrics', 'date', if_not_exists => TRUE);")
                except Exception:
                    pass
                
                # 3. TREND_SCORES TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trend_scores (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        product_id UUID REFERENCES products(id) ON DELETE CASCADE,
                        calculated_date DATE NOT NULL,
                        recency_score DECIMAL(5,2),
                        popularity_score DECIMAL(5,2),
                        velocity_score DECIMAL(5,2),
                        price_position_score DECIMAL(5,2),
                        overall_trend_score DECIMAL(5,2),
                        trend_direction VARCHAR(20),
                        trend_phase VARCHAR(20),
                        demand_velocity INTEGER,
                        momentum DECIMAL(5,2),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id, calculated_date)
                    );
                """)
                
                # 4. ATTRIBUTE_TRENDS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS attribute_trends (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        attribute_category VARCHAR(50),
                        attribute_value VARCHAR(100),
                        month_year DATE NOT NULL,
                        product_count INTEGER,
                        avg_price DECIMAL(10,2),
                        avg_rating DECIMAL(3,2),
                        avg_velocity DECIMAL(10,2),
                        avg_discount DECIMAL(5,2),
                        trend_score DECIMAL(5,2),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(attribute_category, attribute_value, month_year)
                    );
                """)
                
                # 5. SCRAPE_JOBS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scrape_jobs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        job_type VARCHAR(20),
                        platforms TEXT[],
                        status VARCHAR(20),
                        products_scraped INTEGER,
                        products_new INTEGER,
                        products_updated INTEGER,
                        start_time TIMESTAMP,
                        end_time TIMESTAMP,
                        error_log TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_launch_date ON products(launch_date);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_attributes ON products USING GIN(attributes);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trend_scores_date ON trend_scores(calculated_date DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trend_scores_overall ON trend_scores(overall_trend_score DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);")
                
            else:
                # SQLite Setup
                # 1. PRODUCTS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id TEXT PRIMARY KEY,
                        platform TEXT NOT NULL,
                        platform_product_id TEXT,
                        product_url TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        brand TEXT,
                        price REAL,
                        original_price REAL,
                        discount_percentage REAL,
                        rating REAL,
                        review_count INTEGER,
                        image_url TEXT,
                        description TEXT,
                        attributes TEXT DEFAULT '{}',
                        launch_date TEXT,
                        launch_source TEXT,
                        first_seen_date TEXT NOT NULL,
                        last_seen_date TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # 2. DAILY_METRICS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_metrics (
                        id TEXT PRIMARY KEY,
                        product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
                        date TEXT NOT NULL,
                        price REAL,
                        rating REAL,
                        review_count INTEGER,
                        is_in_stock INTEGER DEFAULT 1,
                        rank_on_page INTEGER,
                        daily_review_increment INTEGER DEFAULT 0,
                        estimated_sales_velocity REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id, date)
                    );
                """)
                
                # 3. TREND_SCORES TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trend_scores (
                        id TEXT PRIMARY KEY,
                        product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
                        calculated_date TEXT NOT NULL,
                        recency_score REAL,
                        popularity_score REAL,
                        velocity_score REAL,
                        price_position_score REAL,
                        overall_trend_score REAL,
                        trend_direction TEXT,
                        trend_phase TEXT,
                        demand_velocity INTEGER,
                        momentum REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id, calculated_date)
                    );
                """)
                
                # 4. ATTRIBUTE_TRENDS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS attribute_trends (
                        id TEXT PRIMARY KEY,
                        attribute_category TEXT,
                        attribute_value TEXT,
                        month_year TEXT NOT NULL,
                        product_count INTEGER,
                        avg_price REAL,
                        avg_rating REAL,
                        avg_velocity REAL,
                        avg_discount REAL,
                        trend_score REAL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(attribute_category, attribute_value, month_year)
                    );
                """)
                
                # 5. SCRAPE_JOBS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scrape_jobs (
                        id TEXT PRIMARY KEY,
                        job_type TEXT,
                        platforms TEXT, -- stored as JSON string in SQLite
                        status TEXT,
                        products_scraped INTEGER,
                        products_new INTEGER,
                        products_updated INTEGER,
                        start_time TEXT,
                        end_time TEXT,
                        error_log TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 6. SAVED_PRODUCTS TABLE
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS saved_products (
                        id TEXT PRIMARY KEY,
                        product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(product_id)
                    );
                """)

                # 7. CUSTOM_SOURCES TABLE (User-added Websites/Stores)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS custom_sources (
                        id TEXT PRIMARY KEY,
                        brand_key TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        fallback_url TEXT,
                        base_url TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_launch_date ON products(launch_date);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trend_scores_date ON trend_scores(calculated_date DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_trend_scores_overall ON trend_scores(overall_trend_score DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_products_pid ON saved_products(product_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom_sources_key ON custom_sources(brand_key);")
                
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def serialize_json(self, data: Any) -> str:
        """Serializes dictionary to JSON string"""
        return json.dumps(data, default=str)

    def deserialize_json(self, data_str: Optional[str]) -> Dict[str, Any]:
        """Deserializes JSON string to dictionary"""
        if not data_str:
            return {}
        try:
            return json.loads(data_str)
        except Exception:
            return {}

    def save_products(self, products_list: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Saves products list. Returns (new_count, updated_count)"""
        new_count = 0
        updated_count = 0
        
        conn, cursor = self.get_connection()
        try:
            for p in products_list:
                # Extract clean platform ID and check existence
                platform = p['platform']
                url = p['product_url']
                
                # Standardize attributes format
                attrs = p.get('attributes', {})
                attrs_str = self.serialize_json(attrs) if not self.is_postgres else attrs
                
                # Find if product exists by URL
                if self.is_postgres:
                    cursor.execute("SELECT id FROM products WHERE product_url = %s", (url,))
                else:
                    cursor.execute("SELECT id FROM products WHERE product_url = ?", (url,))
                    
                row = cursor.fetchone()
                
                today_str = date.today().isoformat()
                
                if row:
                    product_id = row['id'] if self.is_postgres else row[0]
                    # Update existing product
                    sql_update = """
                        UPDATE products SET
                            price = %s,
                            original_price = %s,
                            discount_percentage = %s,
                            rating = %s,
                            review_count = %s,
                            image_url = %s,
                            description = %s,
                            attributes = %s,
                            last_seen_date = %s,
                            updated_at = %s
                        WHERE id = %s
                    """
                    params = (
                        p['price'],
                        p.get('original_price'),
                        p.get('discount_percentage'),
                        p['rating'],
                        p['review_count'],
                        p.get('image_url'),
                        p.get('description'),
                        attrs_str,
                        today_str,
                        datetime.now().isoformat(),
                        product_id
                    )
                    
                    if not self.is_postgres:
                        sql_update = sql_update.replace("%s", "?")
                    
                    cursor.execute(sql_update, params)
                    updated_count += 1
                else:
                    # Insert new product
                    product_id = str(uuid.uuid4())
                    launch_date = p.get('launch_date', today_str)
                    
                    sql_insert = """
                        INSERT INTO products (
                            id, platform, platform_product_id, product_url, title, brand,
                            price, original_price, discount_percentage, rating, review_count,
                            image_url, description, attributes, launch_date, launch_source,
                            first_seen_date, last_seen_date, is_active, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """
                    
                    params = (
                        product_id,
                        platform,
                        p.get('platform_product_id'),
                        url,
                        p['title'],
                        p.get('brand'),
                        p['price'],
                        p.get('original_price'),
                        p.get('discount_percentage'),
                        p['rating'],
                        p['review_count'],
                        p.get('image_url'),
                        p.get('description'),
                        attrs_str,
                        launch_date,
                        p.get('launch_source', 'estimated'),
                        today_str,
                        today_str,
                        1,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    )
                    
                    if not self.is_postgres:
                        sql_insert = sql_insert.replace("%s", "?")
                        
                    cursor.execute(sql_insert, params)
                    new_count += 1
            
            conn.commit()
            return new_count, updated_count
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_all_products(self, limit: int = 100, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all products in a flat list of dicts with optional keyword filtering"""
        where_clause = ""
        params = []
        if keyword and keyword.strip():
            where_clause = "WHERE (LOWER(p.title) LIKE %s OR LOWER(p.description) LIKE %s)"
            kw_pattern = f"%{keyword.strip().lower()}%"
            params.extend([kw_pattern, kw_pattern])
            
        sql = f"""
            SELECT p.*, ts.overall_trend_score, ts.trend_direction, ts.trend_phase 
            FROM products p
            LEFT JOIN trend_scores ts ON p.id = ts.product_id AND ts.calculated_date = (
                SELECT MAX(calculated_date) FROM trend_scores WHERE product_id = p.id
            )
            {where_clause}
            ORDER BY p.created_at DESC
            LIMIT %s
        """
        params.append(limit)
        rows = self.execute_query(sql, tuple(params))
        for r in rows:
            if not self.is_postgres and isinstance(r.get('attributes'), str):
                r['attributes'] = self.deserialize_json(r['attributes'])
        return rows

    def get_trending_products(
        self,
        limit: int = 20,
        min_rating: float = 0.0,
        min_reviews: int = 0,
        price_min: float = 0.0,
        price_max: float = 99999.0,
        platforms: List[str] = None,
        keyword: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries products filtered and ordered by overall trend score"""
        # Build dynamic queries
        conditions = ["p.rating >= %s", "p.review_count >= %s", "p.price >= %s", "p.price <= %s"]
        params = [min_rating, min_reviews, price_min, price_max]
        
        if platforms:
            platform_placeholders = ",".join([self.placeholder] * len(platforms))
            conditions.append(f"p.platform IN ({platform_placeholders})")
            params.extend(platforms)

        if keyword and keyword.strip():
            conditions.append("(LOWER(p.title) LIKE %s OR LOWER(p.description) LIKE %s)")
            kw_pattern = f"%{keyword.strip().lower()}%"
            params.extend([kw_pattern, kw_pattern])
            
        where_clause = " AND ".join(conditions)
        
        sql = f"""
            SELECT p.*, 
                   ts.overall_trend_score as trend_score, 
                   ts.trend_direction, 
                   ts.trend_phase,
                   ts.velocity_score,
                   ts.recency_score,
                   ts.popularity_score,
                   ts.price_position_score,
                   ts.demand_velocity,
                   ts.momentum
            FROM products p
            JOIN trend_scores ts ON p.id = ts.product_id
            WHERE {where_clause}
              AND ts.calculated_date = (
                  SELECT MAX(calculated_date) FROM trend_scores WHERE product_id = p.id
              )
            ORDER BY ts.overall_trend_score DESC
            LIMIT %s
        """
        params.append(limit)
        
        rows = self.execute_query(sql, tuple(params))
        for r in rows:
            if not self.is_postgres and isinstance(r.get('attributes'), str):
                r['attributes'] = self.deserialize_json(r['attributes'])
                
            # Simulate "is_new" field if launched within 14 days
            if r.get('launch_date'):
                launch = r['launch_date']
                if isinstance(launch, str):
                    launch = datetime.strptime(launch.split("T")[0], "%Y-%m-%d").date()
                days_old = (date.today() - launch).days
                r['is_new'] = days_old <= 14
                r['days_since_launch'] = days_old
                    
        return rows

    def save_daily_metrics(self, product_id: str, metric_date: str, price: float, rating: float, review_count: int, is_in_stock: bool = True, rank_on_page: int = 1) -> None:
        """Saves daily metric record. Recalculates increment from previous date if exists."""
        # Find previous metric review count to calculate increment
        prev_sql = """
            SELECT review_count FROM daily_metrics 
            WHERE product_id = %s AND date < %s 
            ORDER BY date DESC LIMIT 1
        """
        rows = self.execute_query(prev_sql, (product_id, metric_date))
        daily_increment = 0
        if rows:
            prev_reviews = rows[0]['review_count']
            daily_increment = max(0, review_count - prev_reviews)
            
        sql = """
            INSERT INTO daily_metrics (
                id, product_id, date, price, rating, review_count, is_in_stock, rank_on_page, daily_review_increment, estimated_sales_velocity, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (product_id, date) DO UPDATE SET
                price = EXCLUDED.price,
                rating = EXCLUDED.rating,
                review_count = EXCLUDED.review_count,
                is_in_stock = EXCLUDED.is_in_stock,
                rank_on_page = EXCLUDED.rank_on_page,
                daily_review_increment = EXCLUDED.daily_review_increment,
                estimated_sales_velocity = EXCLUDED.estimated_sales_velocity
        """
        
        # Calculate a simple estimate for sales velocity (approx reviews increment / review rate)
        estimated_sales_velocity = float(daily_increment * 5) # assume 1 review = 5 sales
        
        params = (
            str(uuid.uuid4()),
            product_id,
            metric_date,
            price,
            rating,
            review_count,
            1 if is_in_stock else 0,
            rank_on_page,
            daily_increment,
            estimated_sales_velocity,
            datetime.now().isoformat()
        )
        
        if not self.is_postgres:
            # SQLite does not support ON CONFLICT ... DO UPDATE exactly this way before v3.24
            # We can use INSERT OR REPLACE or handle update manually
            sql_check = "SELECT id FROM daily_metrics WHERE product_id = ? AND date = ?"
            chk_rows = self.execute_query(sql_check, (product_id, metric_date))
            if chk_rows:
                sql = """
                    UPDATE daily_metrics SET
                        price = ?, rating = ?, review_count = ?, is_in_stock = ?, 
                        rank_on_page = ?, daily_review_increment = ?, estimated_sales_velocity = ?
                    WHERE product_id = ? AND date = ?
                """
                params = (price, rating, review_count, 1 if is_in_stock else 0, rank_on_page, daily_increment, estimated_sales_velocity, product_id, metric_date)
            else:
                sql = """
                    INSERT INTO daily_metrics (
                        id, product_id, date, price, rating, review_count, is_in_stock, rank_on_page, daily_review_increment, estimated_sales_velocity, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
        self.execute_write(sql, params)

    def save_trend_score(self, product_id: str, date_str: str, scores: Dict[str, Any]) -> None:
        """Saves scoring details for a specific day"""
        sql = """
            INSERT INTO trend_scores (
                id, product_id, calculated_date, recency_score, popularity_score, velocity_score,
                price_position_score, overall_trend_score, trend_direction, trend_phase, demand_velocity, momentum, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON CONFLICT (product_id, calculated_date) DO UPDATE SET
                recency_score = EXCLUDED.recency_score,
                popularity_score = EXCLUDED.popularity_score,
                velocity_score = EXCLUDED.velocity_score,
                price_position_score = EXCLUDED.price_position_score,
                overall_trend_score = EXCLUDED.overall_trend_score,
                trend_direction = EXCLUDED.trend_direction,
                trend_phase = EXCLUDED.trend_phase,
                demand_velocity = EXCLUDED.demand_velocity,
                momentum = EXCLUDED.momentum
        """
        params = (
            str(uuid.uuid4()),
            product_id,
            date_str,
            scores['recency_score'],
            scores['popularity_score'],
            scores['velocity_score'],
            scores['price_position_score'],
            scores['overall_trend_score'],
            scores['trend_direction'],
            scores['trend_phase'],
            scores.get('demand_velocity', 0),
            scores.get('momentum', 0.0),
            datetime.now().isoformat()
        )
        
        if not self.is_postgres:
            chk_rows = self.execute_query("SELECT id FROM trend_scores WHERE product_id = ? AND calculated_date = ?", (product_id, date_str))
            if chk_rows:
                sql = """
                    UPDATE trend_scores SET
                        recency_score = ?, popularity_score = ?, velocity_score = ?, price_position_score = ?,
                        overall_trend_score = ?, trend_direction = ?, trend_phase = ?, demand_velocity = ?, momentum = ?
                    WHERE product_id = ? AND calculated_date = ?
                """
                params = (
                    scores['recency_score'], scores['popularity_score'], scores['velocity_score'], scores['price_position_score'],
                    scores['overall_trend_score'], scores['trend_direction'], scores['trend_phase'], scores.get('demand_velocity', 0),
                    scores.get('momentum', 0.0), product_id, date_str
                )
            else:
                sql = """
                    INSERT INTO trend_scores (
                        id, product_id, calculated_date, recency_score, popularity_score, velocity_score,
                        price_position_score, overall_trend_score, trend_direction, trend_phase, demand_velocity, momentum, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
        self.execute_write(sql, params)

    def save_daily_metrics_batch(self, metrics_list: List[Dict[str, Any]]) -> None:
        """Saves a batch of daily metric records in a single fast transaction."""
        if not metrics_list:
            return
            
        conn, cursor = self.get_connection()
        try:
            now_iso = datetime.now().isoformat()
            if self.is_postgres:
                sql = """
                    INSERT INTO daily_metrics (
                        id, product_id, date, price, rating, review_count, is_in_stock, rank_on_page, daily_review_increment, estimated_sales_velocity, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id, date) DO UPDATE SET
                        price = EXCLUDED.price,
                        rating = EXCLUDED.rating,
                        review_count = EXCLUDED.review_count,
                        is_in_stock = EXCLUDED.is_in_stock,
                        rank_on_page = EXCLUDED.rank_on_page,
                        daily_review_increment = EXCLUDED.daily_review_increment,
                        estimated_sales_velocity = EXCLUDED.estimated_sales_velocity
                """
                params = [
                    (
                        str(uuid.uuid4()), m['product_id'], m['date'], m['price'], m['rating'],
                        m['review_count'], 1 if m.get('is_in_stock', True) else 0,
                        m.get('rank_on_page', 1), m.get('daily_review_increment', 0),
                        m.get('estimated_sales_velocity', 0.0), now_iso
                    )
                    for m in metrics_list
                ]
                cursor.executemany(sql, params)
            else:
                # SQLite INSERT OR REPLACE for maximum bulk insertion speed
                sql = """
                    INSERT OR REPLACE INTO daily_metrics (
                        id, product_id, date, price, rating, review_count, is_in_stock, rank_on_page, daily_review_increment, estimated_sales_velocity, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    (
                        str(uuid.uuid4()), m['product_id'], m['date'], m['price'], m['rating'],
                        m['review_count'], 1 if m.get('is_in_stock', True) else 0,
                        m.get('rank_on_page', 1), m.get('daily_review_increment', 0),
                        m.get('estimated_sales_velocity', 0.0), now_iso
                    )
                    for m in metrics_list
                ]
                cursor.executemany(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def save_trend_scores_batch(self, scores_list: List[Dict[str, Any]]) -> None:
        """Saves a batch of trend score records in a single fast transaction."""
        if not scores_list:
            return
            
        conn, cursor = self.get_connection()
        try:
            now_iso = datetime.now().isoformat()
            if self.is_postgres:
                sql = """
                    INSERT INTO trend_scores (
                        id, product_id, calculated_date, recency_score, popularity_score, velocity_score,
                        price_position_score, overall_trend_score, trend_direction, trend_phase, demand_velocity, momentum, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id, calculated_date) DO UPDATE SET
                        recency_score = EXCLUDED.recency_score,
                        popularity_score = EXCLUDED.popularity_score,
                        velocity_score = EXCLUDED.velocity_score,
                        price_position_score = EXCLUDED.price_position_score,
                        overall_trend_score = EXCLUDED.overall_trend_score,
                        trend_direction = EXCLUDED.trend_direction,
                        trend_phase = EXCLUDED.trend_phase,
                        demand_velocity = EXCLUDED.demand_velocity,
                        momentum = EXCLUDED.momentum
                """
                params = [
                    (
                        str(uuid.uuid4()), s['product_id'], s['date'], s['scores']['recency_score'],
                        s['scores']['popularity_score'], s['scores']['velocity_score'], s['scores']['price_position_score'],
                        s['scores']['overall_trend_score'], s['scores']['trend_direction'], s['scores']['trend_phase'],
                        s['scores'].get('demand_velocity', 0), s['scores'].get('momentum', 0.0), now_iso
                    )
                    for s in scores_list
                ]
                cursor.executemany(sql, params)
            else:
                sql = """
                    INSERT OR REPLACE INTO trend_scores (
                        id, product_id, calculated_date, recency_score, popularity_score, velocity_score,
                        price_position_score, overall_trend_score, trend_direction, trend_phase, demand_velocity, momentum, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = [
                    (
                        str(uuid.uuid4()), s['product_id'], s['date'], s['scores']['recency_score'],
                        s['scores']['popularity_score'], s['scores']['velocity_score'], s['scores']['price_position_score'],
                        s['scores']['overall_trend_score'], s['scores']['trend_direction'], s['scores']['trend_phase'],
                        s['scores'].get('demand_velocity', 0), s['scores'].get('momentum', 0.0), now_iso
                    )
                    for s in scores_list
                ]
                cursor.executemany(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_product_metrics_history(self, product_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Gets price and reviews history for charts"""
        sql = """
            SELECT date, price, rating, review_count, daily_review_increment, estimated_sales_velocity
            FROM daily_metrics
            WHERE product_id = %s
            ORDER BY date ASC
            LIMIT %s
        """
        return self.execute_query(sql, (product_id, limit))

    def log_scrape_job(self, job_type: str, platforms: List[str]) -> str:
        """Logs the start of a scrape job and returns job UUID"""
        job_id = str(uuid.uuid4())
        platforms_val = self.serialize_json(platforms) if not self.is_postgres else platforms
        
        sql = """
            INSERT INTO scrape_jobs (
                id, job_type, platforms, status, products_scraped, products_new, products_updated, start_time, created_at
            ) VALUES (
                %s, %s, %s, %s, 0, 0, 0, %s, %s
            )
        """
        now = datetime.now().isoformat()
        params = (job_id, job_type, platforms_val, 'running', now, now)
        self.execute_write(sql, params)
        return job_id

    def update_scrape_job(self, job_id: str, status: str, scraped: int, new_count: int, updated_count: int, error_log: str = None) -> None:
        """Updates scrape job on completion"""
        sql = """
            UPDATE scrape_jobs SET
                status = %s,
                products_scraped = %s,
                products_new = %s,
                products_updated = %s,
                end_time = %s,
                error_log = %s
            WHERE id = %s
        """
        now = datetime.now().isoformat()
        params = (status, scraped, new_count, updated_count, now, error_log, job_id)
        self.execute_write(sql, params)

    def get_scrape_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves history of scrape jobs"""
        sql = """
            SELECT * FROM scrape_jobs
            ORDER BY created_at DESC
            LIMIT %s
        """
        rows = self.execute_query(sql, (limit,))
        for r in rows:
            if not self.is_postgres and isinstance(r.get('platforms'), str):
                r['platforms'] = self.deserialize_json(r['platforms'])
        return rows

    def calculate_and_save_attribute_trends(self, target_date_str: str) -> None:
        """Aggregates attributes from active products and populates attribute_trends"""
        # Read all products and their current trend score
        sql_products = """
            SELECT p.id, p.price, p.rating, p.discount_percentage, p.attributes, ts.overall_trend_score, ts.velocity_score
            FROM products p
            JOIN trend_scores ts ON p.id = ts.product_id
            WHERE ts.calculated_date = (
                SELECT MAX(calculated_date) FROM trend_scores WHERE product_id = p.id
            )
        """
        products = self.execute_query(sql_products)
        
        # Aggregate by attribute category and value
        # attributes schema: {"neckline": "V-neck", "fabric": "Cotton", "pattern": "Floral", "sleeve_type": "3/4"}
        aggregations = {} # keys: (category, value) -> list of products
        
        for p in products:
            attrs = p['attributes']
            if isinstance(attrs, str):
                attrs = self.deserialize_json(attrs)
            if not attrs or not isinstance(attrs, dict):
                continue
                
            for cat, val in attrs.items():
                if not val or val.lower() == 'all':
                    continue
                key = (cat, val)
                if key not in aggregations:
                    aggregations[key] = []
                aggregations[key].append(p)
                
        # Parse year-month date
        # E.g. input target_date_str is "2026-08-28" -> month_year date is "2026-08-01"
        target_dt = datetime.strptime(target_date_str.split("T")[0], "%Y-%m-%d")
        month_year_str = date(target_dt.year, target_dt.month, 1).isoformat()
        
        conn, cursor = self.get_connection()
        try:
            for (cat, val), prod_list in aggregations.items():
                count = len(prod_list)
                avg_price = sum(float(p['price']) for p in prod_list) / count
                avg_rating = sum(float(p['rating']) for p in prod_list) / count
                avg_velocity = sum(float(p.get('velocity_score', 0) or 0) for p in prod_list) / count
                avg_discount = sum(float(p.get('discount_percentage', 0) or 0) for p in prod_list) / count
                avg_trend_score = sum(float(p.get('overall_trend_score', 0) or 0) for p in prod_list) / count
                
                # Write to DB
                sql = """
                    INSERT INTO attribute_trends (
                        id, attribute_category, attribute_value, month_year, product_count,
                        avg_price, avg_rating, avg_velocity, avg_discount, trend_score, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (attribute_category, attribute_value, month_year) DO UPDATE SET
                        product_count = EXCLUDED.product_count,
                        avg_price = EXCLUDED.avg_price,
                        avg_rating = EXCLUDED.avg_rating,
                        avg_velocity = EXCLUDED.avg_velocity,
                        avg_discount = EXCLUDED.avg_discount,
                        trend_score = EXCLUDED.trend_score
                """
                params = (
                    str(uuid.uuid4()), cat, val, month_year_str, count,
                    avg_price, avg_rating, avg_velocity, avg_discount, avg_trend_score,
                    datetime.now().isoformat()
                )
                
                if not self.is_postgres:
                    # SQLite fallback
                    sql_chk = """
                        SELECT id FROM attribute_trends 
                        WHERE attribute_category = ? AND attribute_value = ? AND month_year = ?
                    """
                    chk = cursor.execute(sql_chk, (cat, val, month_year_str)).fetchone()
                    if chk:
                        sql = """
                            UPDATE attribute_trends SET
                                product_count = ?, avg_price = ?, avg_rating = ?,
                                avg_velocity = ?, avg_discount = ?, trend_score = ?
                            WHERE attribute_category = ? AND attribute_value = ? AND month_year = ?
                        """
                        params = (count, avg_price, avg_rating, avg_velocity, avg_discount, avg_trend_score, cat, val, month_year_str)
                    else:
                        sql = """
                            INSERT INTO attribute_trends (
                                id, attribute_category, attribute_value, month_year, product_count,
                                avg_price, avg_rating, avg_velocity, avg_discount, trend_score, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        
                cursor.execute(sql, params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_attribute_trends(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns aggregated monthly attribute trends"""
        sql = """
            SELECT * FROM attribute_trends
            ORDER BY month_year DESC, trend_score DESC
            LIMIT %s
        """
        return self.execute_query(sql, (limit,))

    def get_all_time_demand_products(self, limit: int = 50, keyword: str = None) -> List[Dict[str, Any]]:
        """Returns all-time top demand products ranked by highest review count and trend score"""
        where_clause = ""
        params = []
        if keyword and keyword.strip():
            where_clause = "WHERE (LOWER(p.title) LIKE %s OR LOWER(p.description) LIKE %s)"
            kw_pattern = f"%{keyword.strip().lower()}%"
            params.extend([kw_pattern, kw_pattern])

        sql = f"""
            SELECT p.*,
                   ts.overall_trend_score,
                   ts.trend_direction,
                   ts.trend_phase,
                   ts.velocity_score,
                   ts.recency_score,
                   ts.popularity_score,
                   ts.price_position_score,
                   ts.demand_velocity,
                   ts.momentum,
                   (
                       SELECT MAX(review_count) FROM daily_metrics WHERE product_id = p.id
                   ) AS peak_reviews,
                   (
                       SELECT SUM(daily_review_increment) FROM daily_metrics WHERE product_id = p.id
                   ) AS total_review_increments
            FROM products p
            LEFT JOIN trend_scores ts ON p.id = ts.product_id AND ts.calculated_date = (
                SELECT MAX(calculated_date) FROM trend_scores WHERE product_id = p.id
            )
            {where_clause}
            ORDER BY p.review_count DESC, ts.overall_trend_score DESC
            LIMIT %s
        """
        params.append(limit)
        rows = self.execute_query(sql, tuple(params))
        for r in rows:
            if not self.is_postgres and isinstance(r.get('attributes'), str):
                r['attributes'] = self.deserialize_json(r['attributes'])
            if r.get('launch_date'):
                launch = r['launch_date']
                if isinstance(launch, str):
                    launch = datetime.strptime(launch.split("T")[0], "%Y-%m-%d").date()
                r['days_since_launch'] = (date.today() - launch).days
        return rows

    def bookmark_product(self, product_id: str) -> bool:
        """Saves a product to bookmarks table"""
        conn, cursor = self.get_connection()
        try:
            sql = "INSERT INTO saved_products (id, product_id, created_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
            if not self.is_postgres:
                sql = "INSERT OR IGNORE INTO saved_products (id, product_id, created_at) VALUES (?, ?, ?)"
            cursor.execute(sql, (str(uuid.uuid4()), product_id, datetime.now().isoformat()))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    def remove_saved_product(self, product_id: str) -> bool:
        """Removes a product from bookmarks"""
        conn, cursor = self.get_connection()
        try:
            sql = "DELETE FROM saved_products WHERE product_id = %s"
            if not self.is_postgres:
                sql = "DELETE FROM saved_products WHERE product_id = ?"
            cursor.execute(sql, (product_id,))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    def get_saved_products(self) -> List[Dict[str, Any]]:
        """Retrieves all saved products with their latest trend scores and attributes"""
        sql = """
            SELECT p.*,
                   ts.overall_trend_score as trend_score,
                   ts.velocity_score,
                   ts.recency_score,
                   ts.popularity_score,
                   ts.price_position_score,
                   ts.trend_direction,
                   ts.trend_phase,
                   ts.demand_velocity,
                   ts.momentum,
                   sp.created_at as saved_at
            FROM saved_products sp
            JOIN products p ON sp.product_id = p.id
            LEFT JOIN trend_scores ts ON p.id = ts.product_id AND ts.calculated_date = (
                SELECT MAX(calculated_date) FROM trend_scores WHERE product_id = p.id
            )
            ORDER BY sp.created_at DESC
        """
        rows = self.execute_query(sql)
        for r in rows:
            if not self.is_postgres and isinstance(r.get('attributes'), str):
                r['attributes'] = self.deserialize_json(r['attributes'])
            if r.get('launch_date'):
                launch = r['launch_date']
                if isinstance(launch, str):
                    launch = datetime.strptime(launch.split("T")[0], "%Y-%m-%d").date()
                r['days_since_launch'] = (date.today() - launch).days
        return rows

    def add_custom_source(self, brand_key: str, name: str, url: str, fallback_url: str = None, base_url: str = None) -> bool:
        """Adds a custom website / store feed to the database"""
        conn, cursor = self.get_connection()
        try:
            sql = """
                INSERT INTO custom_sources (id, brand_key, name, url, fallback_url, base_url, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (brand_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    url = EXCLUDED.url,
                    fallback_url = EXCLUDED.fallback_url,
                    base_url = EXCLUDED.base_url
            """
            if not self.is_postgres:
                sql = """
                    INSERT INTO custom_sources (id, brand_key, name, url, fallback_url, base_url, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(brand_key) DO UPDATE SET
                        name=excluded.name,
                        url=excluded.url,
                        fallback_url=excluded.fallback_url,
                        base_url=excluded.base_url
                """
            cursor.execute(sql, (
                str(uuid.uuid4()),
                brand_key.lower().replace(" ", "").replace("_", ""),
                name.strip(),
                url.strip(),
                fallback_url.strip() if fallback_url else url.strip(),
                base_url.strip() if base_url else (url.split('?')[0].rstrip('/') + '/'),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

    def get_custom_sources(self) -> List[Dict[str, Any]]:
        """Retrieves all user-added custom store feeds"""
        sql = "SELECT * FROM custom_sources ORDER BY created_at DESC"
        return self.execute_query(sql)

    def delete_custom_source(self, brand_key: str) -> bool:
        """Removes a custom website source"""
        conn, cursor = self.get_connection()
        try:
            sql = "DELETE FROM custom_sources WHERE brand_key = %s"
            if not self.is_postgres:
                sql = "DELETE FROM custom_sources WHERE brand_key = ?"
            cursor.execute(sql, (brand_key.lower().replace(" ", ""),))
            conn.commit()
            return True
        finally:
            cursor.close()
            conn.close()

