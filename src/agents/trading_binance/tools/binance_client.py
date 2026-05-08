import logging
import os
from typing import Any, Dict, Tuple

import ccxt

from src.config.settings import settings

logger = logging.getLogger(__name__)


class BinanceClient:
    def __init__(self, use_testnet: bool = True):
        self.api_key = settings.binance_api_key
        self.secret_key = settings.binance_secret_key

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Missing BINANCE_API_KEY or BINANCE_SECRET_KEY in .env file"
            )

        self.exchange = ccxt.binance(
            {
                "apiKey": self.api_key,
                "secret": self.secret_key,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )

        if use_testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("🔧 BinanceClient is running in TESTNET mode.")

    def fetch_balances(self) -> Tuple[float, float]:
        """Fetch current USDT and XAUT balances."""
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance["USDT"]["free"] if "USDT" in balance else 0.0
            xaut = balance["XAUT"]["free"] if "XAUT" in balance else 0.0
            return float(usdt), float(xaut)
        except Exception as e:
            logger.error(f"Error fetching balances: {e}")
            raise e

    def fetch_price(self, symbol: str = "XAUT/USDT") -> float:
        """Fetch latest Spot price."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise e

    def execute_trade(
        self, action: str, amount_usd: float, symbol: str = "XAUT/USDT"
    ) -> Dict[str, Any]:
        """
        Execute Market Buy or Market Sell order based on specified USD amount.
        """
        try:
            current_price = self.fetch_price(symbol)

            # Calculate base asset quantity (XAUT)
            # Round to 5 decimal places to avoid Binance precision errors
            amount_xaut = round(amount_usd / current_price, 5)

            logger.info(
                f"Preparing to {action} {amount_xaut} XAUT (~${amount_usd} USDT) at Market price {current_price}"
            )

            if action == "BUY":
                # Execute BUY API
                order = self.exchange.create_market_buy_order(symbol, amount_xaut)
                return order
            elif action == "SELL":
                # Execute SELL API
                order = self.exchange.create_market_sell_order(symbol, amount_xaut)
                return order
            else:
                raise ValueError(f"Invalid action: {action}")

        except Exception as e:
            logger.error(f"Error executing {action} order for {symbol}: {e}")
            raise e

    def execute_limit_trade(
        self,
        action: str,
        amount_usd: float,
        limit_price: float,
        symbol: str = "XAUT/USDT",
    ) -> Dict[str, Any]:
        """
        Execute Limit Buy or Limit Sell order based on specified USD amount and target Limit price.
        """
        try:
            # Calculate base asset quantity (XAUT) using the exact Limit price
            # Round to 5 decimal places to avoid Binance precision errors
            amount_xaut = round(amount_usd / limit_price, 5)

            logger.info(
                f"Preparing to {action} {amount_xaut} XAUT (~${amount_usd} USDT) at LIMIT price {limit_price}"
            )

            if action == "BUY":
                order = self.exchange.create_limit_buy_order(
                    symbol, amount_xaut, limit_price
                )
                return order
            elif action == "SELL":
                order = self.exchange.create_limit_sell_order(
                    symbol, amount_xaut, limit_price
                )
                return order
            else:
                raise ValueError(f"Invalid action: {action}")

        except Exception as e:
            logger.error(f"Error executing {action} limit order for {symbol}: {e}")
            raise e
