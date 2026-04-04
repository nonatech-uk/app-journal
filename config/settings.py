from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres — journal database
    db_host: str = "192.168.128.9"
    db_port: int = 5432
    db_name: str = "journal"
    db_user: str = "journal"
    db_password: str = ""
    db_sslmode: str = "require"

    # Cross-DB connections (for enrichment)
    finance_db_name: str = "finance"
    finance_db_user: str = "finance"
    finance_db_password: str = ""
    mylocation_db_name: str = "mylocation"
    mylocation_db_user: str = "mylocation"
    mylocation_db_password: str = ""
    scrobble_db_name: str = "scrobble"
    scrobble_db_user: str = "scrobble"
    scrobble_db_password: str = ""

    # External services
    immich_url: str = "http://localhost:2283"
    immich_public_url: str = "https://pix.mees.st"
    immich_api_key: str = ""
    paperless_url: str = "http://localhost:8000"
    paperless_api_token: str = ""
    tautulli_url: str = "http://localhost:8181"
    tautulli_api_key: str = ""
    openai_api_key: str = ""
    mylocation_public_url: str = "https://locs.mees.st"

    # Pipeline ingest
    pipeline_secret: str = ""

    # Flight enrichment
    flightaware_api_key: str = ""
    flight_image_cache_dir: str = "/data/journal/flight-images"

    # Media — path to journal media files
    media_root: str = "/data/journal/media"

    # Auth
    auth_enabled: bool = True
    dev_user_email: str = "stu@mees.st"
    cors_origins: list[str] = [
        "https://journal.mees.st",
        "http://localhost:5173",
    ]

    # Usage tracking
    usage_dsn: str = ""

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    db_pool_min: int = 2
    db_pool_max: int = 10

    model_config = {
        "env_file": str(Path(__file__).resolve().parent / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def dsn(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} sslmode={self.db_sslmode}"
        )

    def cross_dsn(self, db_name: str, db_user: str, db_password: str) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={db_name} "
            f"user={db_user} password={db_password} sslmode={self.db_sslmode}"
        )


settings = Settings()
