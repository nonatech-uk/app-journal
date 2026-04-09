from pathlib import Path

from mees_shared.settings import BaseAppSettings


class Settings(BaseAppSettings):
    db_host: str = "192.168.128.9"
    db_name: str = "journal"
    db_user: str = "journal"
    db_sslmode: str = "require"

    cors_origins: list[str] = [
        "https://journal.mees.st",
        "http://localhost:5173",
    ]

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
    immich_tag_api_key: str = ""
    paperless_url: str = "http://localhost:8000"
    paperless_api_token: str = ""
    tautulli_url: str = "http://localhost:8181"
    tautulli_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    mylocation_public_url: str = "https://locs.mees.st"

    # Immich album exclusion
    immich_album_exclude_patterns: str = "^_"

    # Pipeline ingest
    pipeline_secret: str = ""

    # Flight enrichment
    flightaware_api_key: str = ""
    flight_image_cache_dir: str = "/data/journal/flight-images"
    iaa_register_path: str = "/data/journal/iaa-register.xls"
    airframes_org_user: str = ""
    airframes_org_password: str = ""

    # Media
    media_root: str = "/data/journal/media"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
