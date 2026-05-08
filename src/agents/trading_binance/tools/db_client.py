import json
import logging
import os
import sqlite3
from typing import Any, Dict, List

from src.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    def __init__(self, db_path: str = "trading_memory.db"):
        # Check if environment variable overrides the path
        env_db_path = settings.trading_memory_db_path
        if env_db_path:
            self.db_path = env_db_path
        else:
            # Ensure correct path regardless of where this is called from
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            if not os.path.isabs(db_path):
                self.db_path = os.path.join(root_dir, db_path)
            else:
                self.db_path = db_path

        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Create database tables for accounting."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        amount_xaut REAL NOT NULL,
                        price REAL NOT NULL,
                        cost_usdt REAL NOT NULL,
                        fee_currency TEXT,
                        fee_amount REAL,
                        signal_id INTEGER
                    )
                """)

                try:
                    cursor.execute(
                        "ALTER TABLE trade_history ADD COLUMN signal_id INTEGER"
                    )
                except sqlite3.OperationalError:
                    pass

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS macro_cycles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cycle_type TEXT NOT NULL,
                        start_date DATETIME,
                        end_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_accumulated_usd REAL,
                        average_entry_price REAL,
                        average_exit_price REAL,
                        realized_pnl_pct REAL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        final_action TEXT NOT NULL,
                        reasoning TEXT,
                        full_json TEXT
                    )
                """)

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")

    def save_signal(self, final_action: str, reasoning: str, full_json: str) -> int:
        """Save Bot 1 signal to DB and return signal_id."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO daily_signals (final_action, reasoning, full_json)
                    VALUES (?, ?, ?)
                """,
                    (final_action, reasoning, full_json),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving Signal: {e}")
            return -1

    def get_latest_signal(self) -> Dict[str, Any]:
        """Fetch the latest signal analyzed by Bot 1."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, created_at, final_action, reasoning, full_json FROM daily_signals ORDER BY id DESC LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "created_at": row[1],
                        "final_action": row[2],
                        "reasoning": row[3],
                        "full_json": json.loads(row[4]) if row[4] else {},
                    }
                return {}
        except Exception as e:
            logger.error(f"Error fetching Latest Signal: {e}")
            return {}

    def is_signal_executed(self, signal_id: int) -> bool:
        """Check if this signal_id has already been traded (Anti double-spend)."""
        if not signal_id or signal_id <= 0:
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT count(*) FROM trade_history WHERE signal_id = ?",
                    (signal_id,),
                )
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Idempotency check error: {e}")
            return False

    def save_trade(self, order_data: Dict[str, Any], signal_id: int = None) -> bool:
        """Record a successful trade order into DB, attached with signal_id."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                order_id = str(order_data.get("id", ""))
                symbol = order_data.get("symbol", "XAUT/USDT")
                side = str(order_data.get("side", "")).upper()
                amount_xaut = float(
                    order_data.get("filled", 0.0) or order_data.get("amount", 0.0)
                )
                cost_usdt = float(order_data.get("cost", 0.0))

                price = float(
                    order_data.get("average", 0.0) or order_data.get("price", 0.0)
                )
                if price == 0 and amount_xaut > 0:
                    price = cost_usdt / amount_xaut

                fee = order_data.get("fee", {})
                fee_currency = fee.get("currency", "") if isinstance(fee, dict) else ""
                fee_amount = (
                    float(fee.get("cost", 0.0)) if isinstance(fee, dict) else 0.0
                )

                cursor.execute(
                    """
                    INSERT INTO trade_history 
                    (order_id, symbol, side, amount_xaut, price, cost_usdt, fee_currency, fee_amount, signal_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        order_id,
                        symbol,
                        side,
                        amount_xaut,
                        price,
                        cost_usdt,
                        fee_currency,
                        fee_amount,
                        signal_id,
                    ),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
            return False

    def get_wac(self) -> float:
        """
        Calculate Weighted Average Cost (WAC).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT side, amount_xaut, cost_usdt FROM trade_history WHERE symbol = 'XAUT/USDT'"
                )
                trades = cursor.fetchall()

                total_xaut_bought = 0.0
                total_usdt_spent = 0.0

                total_xaut_sold = 0.0
                total_usdt_earned = 0.0

                for side, amount, cost in trades:
                    if side == "BUY":
                        total_xaut_bought += amount
                        total_usdt_spent += cost
                    elif side == "SELL":
                        total_xaut_sold += amount
                        total_usdt_earned += cost

                current_xaut_inventory = total_xaut_bought - total_xaut_sold
                net_usdt_investment = total_usdt_spent - total_usdt_earned

                if current_xaut_inventory <= 0.00001:
                    return 0.0

                if net_usdt_investment <= 0:
                    return 0.0

                wac = net_usdt_investment / current_xaut_inventory
                return wac
        except Exception as e:
            logger.error(f"Error calculating WAC: {e}")
            return 0.0
