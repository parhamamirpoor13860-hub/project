"""Central configuration loaded from environment variables with sensible defaults."""
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    tsetmc_base_url: str = os.getenv("TSETMC_BASE_URL", "https://cdn.tsetmc.com/api")
    tsetmc_timeout_seconds: float = float(os.getenv("TSETMC_TIMEOUT_SECONDS", "20"))
    tsetmc_max_rps: float = float(os.getenv("TSETMC_MAX_RPS", "2.0"))
    tsetmc_max_concurrency: int = int(os.getenv("TSETMC_MAX_CONCURRENCY", "2"))
    tsetmc_max_retries: int = int(os.getenv("TSETMC_MAX_RETRIES", "3"))
    tsetmc_start_date: int = int(os.getenv("TSETMC_START_DATE", "20230321"))
    tsetmc_respect_trading_hours: bool = os.getenv("TSETMC_RESPECT_TRADING_HOURS", "true").lower() == "true"
    tsetmc_use_fixtures: bool = os.getenv("TSETMC_USE_FIXTURES", "false").lower() == "true"

    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    raw_dir: Path = Path(os.getenv("RAW_DIR", "./data/raw"))
    processed_dir: Path = Path(os.getenv("PROCESSED_DIR", "./data/processed"))
    fixtures_dir: Path = Path(os.getenv("FIXTURES_DIR", "./data/fixtures"))
    state_db_path: Path = Path(os.getenv("STATE_DB_PATH", "./data/state.sqlite"))
    duckdb_path: Path = Path(os.getenv("DUCKDB_PATH", "./data/market.duckdb"))

    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.raw_dir, self.processed_dir, self.fixtures_dir):
            d.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
