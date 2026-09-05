from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple

class ScoringEngine:
    """Calculates trending metrics and classifications for Kurti products"""

    # Bi-weekly decay tiers (14-day steps, up to 90 days / 3 months)
    BIWEEKLY_TIERS = [
        (0,   14, 100.0, "Week 1-2 (Hot)"),
        (15,  28,  85.0, "Week 3-4"),
        (29,  42,  70.0, "Month 2, Week 1-2"),
        (43,  56,  55.0, "Month 2, Week 3-4"),
        (57,  70,  40.0, "Month 3, Week 1-2"),
        (71,  84,  25.0, "Month 3, Week 3-4"),
        (85, 999,  10.0, "3+ Months Old"),
    ]

    @classmethod
    def get_biweekly_tier(cls, days_since_launch: int) -> Tuple[float, str]:
        """Returns the bi-weekly recency score and label for a given age in days"""
        for (start, end, score, label) in cls.BIWEEKLY_TIERS:
            if start <= days_since_launch <= end:
                return score, label
        return 5.0, "Very Old"

    @classmethod
    def calculate_recency_score(cls, launch_date_val: Any) -> Tuple[float, str]:
        """
        Recency Score (Weight: 25%)
        Decays bi-weekly (every 14 days) from 100 to 10 over 3 months (90 days).
        Returns: (recency_score, tier_label)
        """
        if not launch_date_val:
            return 5.0, "Unknown"

        if isinstance(launch_date_val, str):
            try:
                launch_date = datetime.strptime(launch_date_val.split("T")[0], "%Y-%m-%d").date()
            except Exception:
                return 5.0, "Unknown"
        elif isinstance(launch_date_val, (datetime, date)):
            launch_date = launch_date_val if isinstance(launch_date_val, date) else launch_date_val.date()
        else:
            return 5.0, "Unknown"

        days_since_launch = max(0, (date.today() - launch_date).days)
        score, label = cls.get_biweekly_tier(days_since_launch)
        return float(score), label

    @staticmethod
    def calculate_popularity_score(rating: float, review_count: int) -> float:
        """
        Popularity Score (Weight: 30%)
        Combines product rating (60% weight) and normalized review volume (40% weight).
        """
        rating = float(rating or 0.0)
        review_count = int(review_count or 0)

        rating_weight = rating / 5.0  # Normalized to 0-1
        review_volume_weight = min(1.0, review_count / 1000.0)  # Full score at 1000+ reviews

        popularity_score = (rating_weight * 0.6) + (review_volume_weight * 0.4)
        return float(popularity_score * 100.0)

    @staticmethod
    def calculate_velocity_score(
        launch_date_val: Any,
        current_reviews: int,
        historical_metrics: List[Dict[str, Any]],
        max_velocity: float = 1.0
    ) -> Tuple[float, float]:
        """
        Velocity Score (Weight: 35%)
        Measures reviews increment rate (reviews per day) over the last 7 days.
        Returns: (velocity_score, reviews_per_day)
        """
        current_reviews = int(current_reviews or 0)

        # Calculate days since launch
        if isinstance(launch_date_val, str):
            try:
                launch_date = datetime.strptime(launch_date_val.split("T")[0], "%Y-%m-%d").date()
            except Exception:
                launch_date = date.today()
        elif isinstance(launch_date_val, (datetime, date)):
            launch_date = launch_date_val if isinstance(launch_date_val, date) else launch_date_val.date()
        else:
            launch_date = date.today()

        days_since_launch = max(1, (date.today() - launch_date).days)

        # Determine reviews per day rate
        daily_review_rate = 0.0

        # Look for metric from ~7 days ago
        review_7_days_ago = None
        target_date_7_ago = date.today() - timedelta(days=7)

        # Sort history by date descending
        history_sorted = sorted(
            historical_metrics,
            key=lambda x: x['date'] if isinstance(x['date'], str) else x['date'].isoformat(),
            reverse=True
        )

        for metric in history_sorted:
            m_date_str = metric['date']
            if isinstance(m_date_str, str):
                m_date = datetime.strptime(m_date_str.split("T")[0], "%Y-%m-%d").date()
            else:
                m_date = m_date_str

            # If we find a metric that is 7 or more days ago
            if m_date <= target_date_7_ago:
                review_7_days_ago = int(metric.get('review_count', 0) or 0)
                days_diff = (date.today() - m_date).days
                break

        if review_7_days_ago is not None and current_reviews >= review_7_days_ago:
            recent_reviews = current_reviews - review_7_days_ago
            daily_review_rate = recent_reviews / max(1, days_diff)
        else:
            # Fallback for new products or incomplete history
            daily_review_rate = current_reviews / days_since_launch

        # Normalize velocity score (max observed velocity in dataset)
        max_velocity = max(0.1, max_velocity)
        velocity_score = (daily_review_rate / max_velocity) * 100.0
        velocity_score = min(100.0, max(0.0, velocity_score))

        return float(velocity_score), float(daily_review_rate)

    @staticmethod
    def calculate_price_position_score(price: float, category_avg_price: float, discount_percentage: float) -> float:
        """
        Price Position Score (Weight: 10%)
        Compares price to segment averages, with discount bonus.
        """
        price = float(price or 0.0)
        category_avg_price = float(category_avg_price or price or 1.0)
        discount_percentage = float(discount_percentage or 0.0)

        if category_avg_price == 0.0:
            category_avg_price = price or 1.0

        price_position_ratio = price / category_avg_price

        if price_position_ratio <= 0.7:
            price_position_score = 90.0 + (0.7 - price_position_ratio) * 30.0
        elif price_position_ratio <= 1.0:
            price_position_score = 80.0 - (price_position_ratio - 0.7) * 30.0
        elif price_position_ratio <= 1.3:
            price_position_score = 59.0 - (price_position_ratio - 1.0) * 50.0
        else:
            price_position_score = max(20.0, 44.0 - (price_position_ratio - 1.3) * 20.0)

        # Add discount bonus: Max 20 bonus
        discount_bonus = min(20.0, discount_percentage * 0.4)
        price_position_score = min(100.0, price_position_score + discount_bonus)

        return float(price_position_score)

    @classmethod
    def calculate_overall_scores(
        cls,
        product: Dict[str, Any],
        historical_metrics: List[Dict[str, Any]],
        category_avg_price: float,
        max_velocity: float = 1.0
    ) -> Dict[str, Any]:
        """
        Computes composite scores and classifications.
        """
        launch_date = product.get('launch_date')
        rating = float(product.get('rating', 0.0) or 0.0)
        reviews = int(product.get('review_count', 0) or 0)
        price = float(product.get('price', 0.0) or 0.0)
        discount = float(product.get('discount_percentage', 0.0) or 0.0)

        recency, recency_tier = cls.calculate_recency_score(launch_date)
        popularity = cls.calculate_popularity_score(rating, reviews)
        velocity_score, reviews_per_day = cls.calculate_velocity_score(launch_date, reviews, historical_metrics, max_velocity)
        price_pos = cls.calculate_price_position_score(price, category_avg_price, discount)

        # Composite score
        overall_trend_score = (
            recency * 0.25 +
            popularity * 0.30 +
            velocity_score * 0.35 +
            price_pos * 0.10
        )

        # Days since launch
        if isinstance(launch_date, str):
            try:
                l_date = datetime.strptime(launch_date.split("T")[0], "%Y-%m-%d").date()
            except Exception:
                l_date = date.today()
        elif isinstance(launch_date, (datetime, date)):
            l_date = launch_date if isinstance(launch_date, date) else launch_date.date()
        else:
            l_date = date.today()

        days_since_launch = (date.today() - l_date).days

        # Classification rules
        if overall_trend_score >= 80.0 and velocity_score >= 70.0:
            trend_phase = 'growth'
            trend_direction = 'rising'
        elif overall_trend_score >= 60.0 and velocity_score >= 50.0:
            trend_phase = 'maturity'
            trend_direction = 'stable'
        elif overall_trend_score >= 40.0:
            trend_phase = 'decline'
            trend_direction = 'falling'
        elif days_since_launch <= 14:
            trend_phase = 'introduction'
            trend_direction = 'new'
        else:
            trend_phase = 'decline'
            trend_direction = 'falling'

        # Estimate momentum (change in rating over 7 days)
        momentum = 0.0
        if historical_metrics:
            history_sorted = sorted(historical_metrics, key=lambda x: x['date'], reverse=True)
            for m in history_sorted:
                m_date = m['date']
                if isinstance(m_date, str):
                    m_date = datetime.strptime(m_date.split("T")[0], "%Y-%m-%d").date()
                if (date.today() - m_date).days >= 7:
                    prev_rating = float(m.get('rating', 0.0) or 0.0)
                    momentum = rating - prev_rating
                    break

        return {
            'recency_score': round(recency, 2),
            'recency_tier': recency_tier,
            'popularity_score': round(popularity, 2),
            'velocity_score': round(velocity_score, 2),
            'price_position_score': round(price_pos, 2),
            'overall_trend_score': round(overall_trend_score, 2),
            'trend_direction': trend_direction,
            'trend_phase': trend_phase,
            'demand_velocity': round(reviews_per_day, 2),
            'momentum': round(momentum, 2)
        }
