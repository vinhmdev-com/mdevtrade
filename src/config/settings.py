from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Settings
    llm_api_key: str = "unauth"
    llm_base_url: Optional[str] = None
    llm_fast_model: str = "qwen3:latest"
    llm_deep_model: str = "qwen3:latest"

    # Binance Settings
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    binance_use_testnet: bool = True
    order_size_usd: float = 5.5
    max_xaut_inventory_usd: float = 1000.0

    # DB Settings
    trading_memory_db_path: Optional[str] = None

    # Auto-load values from the .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore env vars not declared here (e.g. LANGSMITH_*)
    )


settings = Settings()
