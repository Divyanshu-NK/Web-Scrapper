import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

class Settings:
    # Apify Credentials
    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    DB_HOST: str = os.getenv("DB_HOST", "")
    DB_PORT: str = os.getenv("DB_PORT", "")
    DB_NAME: str = os.getenv("DB_NAME", "")
    DB_USER: str = os.getenv("DB_USER", "")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    @property
    def is_postgres(self) -> bool:
        # Check if database configuration indicates PostgreSQL
        return bool(self.DATABASE_URL.startswith("postgresql://") or (self.DB_HOST and self.DB_NAME and self.DB_USER))

settings = Settings()
