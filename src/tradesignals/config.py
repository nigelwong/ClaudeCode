from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    sec_edgar_user_agent: str = ""
    fred_api_key: str = ""
    tradesignals_db_path: str = "data/tradesignals.db"

    @property
    def db_path(self) -> Path:
        path = Path(self.tradesignals_db_path)
        return path if path.is_absolute() else REPO_ROOT / path


class CrossAssetConfig(BaseModel):
    sectors: dict[str, str]  # ticker -> sector display name
    bonds: str
    gold: str

    @property
    def tickers(self) -> list[str]:
        return [*self.sectors.keys(), self.bonds, self.gold]


class Watchlist(BaseModel):
    tickers: list[str]
    benchmark: str
    cross_asset: CrossAssetConfig


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_watchlist() -> Watchlist:
    with open(REPO_ROOT / "watchlist.yaml") as f:
        return Watchlist.model_validate(yaml.safe_load(f))
