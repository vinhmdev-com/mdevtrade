import json
import logging
import os
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from src.agents.trading_binance.states.execution_state import ExecutionState
from src.agents.trading_binance.tools.binance_client import BinanceClient
from src.agents.trading_binance.tools.db_client import DatabaseClient
from src.config.settings import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def _action_to_trend(action: str) -> str:
    action = (action or "NEUTRAL").upper()
    if action == "BUY":
        return "BULLISH"
    if action == "SELL":
        return "BEARISH"
    return "NEUTRAL"


def read_brain_signal(state: ExecutionState) -> Dict[str, Any]:
    print("\n[NODE: Read Brain Signal] 🧠 Reading latest signal...")

    # Prefer the signal already in state (when run as a subgraph after Research).
    # This avoids a race where another bot writes to the DB between Research saving
    # and Execution reading "latest".
    upstream_decision = state.get("final_trade_decision") or {}
    if upstream_decision:
        action = upstream_decision.get("Final_Action", "NEUTRAL")
        trend = _action_to_trend(action)
        entry_price = float(upstream_decision.get("Entry_Price", 0.0) or 0.0)
        # signal_id is generated when Research persists to DB but isn't in state,
        # so fall back to the DB id corresponding to the latest row.
        signal_id = state.get("signal_id") or 0
        if not signal_id:
            try:
                latest_signal = DatabaseClient().get_latest_signal() or {}
                signal_id = latest_signal.get("id", 0)
            except Exception as e:
                print(f" ⚠️ Could not resolve signal_id from DB: {e}")

        print(f" => 🎯 Using upstream decision: {trend} (signal_id={signal_id})")
        if entry_price > 0:
            print(f" => 🎯 Suggested Entry Price: {entry_price}")

        return {
            "macro_trend": trend,
            "signal_id": signal_id,
            "entry_price": entry_price,
        }

    # Fallback: standalone execution path reads the latest signal from SQLite.
    print(" - No upstream decision in state, falling back to SQLite (Bot 1)...")
    try:
        db = DatabaseClient()
        latest_signal = db.get_latest_signal()

        if not latest_signal:
            print(" ❌ No signals found in Database!")
            return {"macro_trend": "NEUTRAL", "action_taken": "SKIP"}

        signal_id = latest_signal.get("id")
        trend = _action_to_trend(latest_signal.get("final_action"))

        print(f" => 🎯 Fetched Signal ID: {signal_id}")
        print(f" => 🎯 Analyzed Signal: {trend}")

        full_json = latest_signal.get("full_json", {})
        entry_price = float(full_json.get("Entry_Price", 0.0) or 0.0)
        if entry_price > 0:
            print(f" => 🎯 Suggested Entry Price: {entry_price}")

        return {
            "macro_trend": trend,
            "signal_id": signal_id,
            "entry_price": entry_price,
        }
    except Exception as e:
        print(f" ❌ Database read error: {e}")
        return {"macro_trend": "NEUTRAL", "action_taken": "SKIP"}


def check_constraints(state: ExecutionState) -> Dict[str, Any]:
    print("\n[NODE: Constraint Checker] 🛡️ Checking Idempotency, WAC & Inventory...")

    if state.get("action_taken") in ["PAUSE", "SKIP"]:
        return {}

    db = DatabaseClient()
    signal_id = state.get("signal_id")

    if signal_id and db.is_signal_executed(signal_id):
        print(f" ⚠️ WARNING: Signal ID {signal_id} HAS ALREADY BEEN EXECUTED!")
        print(" ⛔ Cancelling order to prevent double-spend.")
        return {"action_taken": "SKIP", "action_message": "Duplicate Signal ID"}

    wac = db.get_wac()
    print(f" => Weighted Average Cost (WAC): {wac:.2f} USDT")

    max_inventory = settings.max_xaut_inventory_usd

    current_xaut_usd = state.get("xaut_balance", 0.0) * state.get("current_price", 0.0)
    print(f" => Total XAUT Value: {current_xaut_usd:.2f} USDT")

    if current_xaut_usd >= max_inventory:
        print(
            f" ⚠️ WARNING: Reached Max Inventory threshold (${max_inventory}). BUY orders will be blocked."
        )

    return {"portfolio_value": wac}


def read_binance_data(state: ExecutionState) -> Dict[str, Any]:
    print("\n[NODE: Read Binance Data] 📡 Reading Spot wallet status...")
    try:
        client = BinanceClient(use_testnet=settings.binance_use_testnet)
        usdt, xaut = client.fetch_balances()
        price = client.fetch_price()

        print(f" => Wallet: {usdt:.2f} USDT | {xaut:.4f} XAUT")
        print(f" => Market Price: 1 XAUT = {price:.2f} USDT")

        return {"usdt_balance": usdt, "xaut_balance": xaut, "current_price": price}
    except Exception as e:
        print(f" ❌ Binance Connection Error: {e}")
        return {"action_taken": "PAUSE", "action_message": "Binance API Error"}


def execute_trade(state: ExecutionState) -> Dict[str, Any]:
    print("\n[NODE: Execute Trade] ⚡ Making execution decision & Sending order...")

    if state.get("action_taken") in ["PAUSE", "SKIP"]:
        print(" - System is PAUSED/SKIPPED. Skipping trade execution.")
        return {}

    trend = state.get("macro_trend", "NEUTRAL")

    if trend == "NEUTRAL":
        print(" - Signal: NEUTRAL -> DO NOTHING")
        return {
            "action_taken": "SKIP",
            "action_amount": 0.0,
            "action_message": "No clear trend",
        }

    order_size = settings.order_size_usd
    max_inventory = settings.max_xaut_inventory_usd

    usdt_bal = state.get("usdt_balance", 0)
    xaut_bal = state.get("xaut_balance", 0)
    price = state.get("current_price", 0)
    entry_price = state.get("entry_price", 0.0)

    db = DatabaseClient()
    wac = db.get_wac()

    try:
        client = BinanceClient(use_testnet=settings.binance_use_testnet)

        if trend == "BULLISH":
            print(f" - Signal: BULLISH -> BUY {order_size}$ XAUT")

            if usdt_bal < 5.0:
                print(" ❌ Not enough USDT to buy (Min 5$)")
                return {"action_taken": "SKIP"}

            current_xaut_usd = xaut_bal * price
            if current_xaut_usd + order_size > max_inventory:
                print(f" ❌ BUY REJECTED: Will exceed Max Inventory (${max_inventory})")
                return {"action_taken": "SKIP"}

            actual_size = min(order_size, usdt_bal)

            if entry_price > 0:
                print(f" => 🎯 Placing LIMIT BUY at {entry_price}")
                order = client.execute_limit_trade("BUY", actual_size, entry_price)
            else:
                print(f" => ⚠️ No Entry_Price found. Placing MARKET BUY")
                order = client.execute_trade("BUY", actual_size)

            print(f" => ✅ BUY order successfully filled! Order ID: {order['id']}")

            # Save to history
            signal_id = state.get("signal_id")
            db.save_trade(order, signal_id)



            return {
                "action_taken": "BUY",
                "action_amount": actual_size,
                "action_message": f"Buy successful: {order['id']}",
            }

        elif trend == "BEARISH":
            print(f" - Signal: BEARISH -> SELL {order_size}$ XAUT")

            xaut_usd_value = xaut_bal * price
            if xaut_usd_value < 5.0:
                print(" ❌ Not enough XAUT to sell (Min 5$)")
                return {"action_taken": "SKIP"}

            if price < wac:
                print(
                    f" ⛔ SELL REJECTED: Market Price ({price:.2f}) < WAC ({wac:.2f}). SWITCHING TO HOLD MODE."
                )
                return {"action_taken": "SKIP"}

            actual_size = min(order_size, xaut_usd_value)

            if entry_price > 0:
                print(f" => 🎯 Placing LIMIT SELL at {entry_price}")
                order = client.execute_limit_trade("SELL", actual_size, entry_price)
            else:
                print(f" => ⚠️ No Entry_Price found. Placing MARKET SELL")
                order = client.execute_trade("SELL", actual_size)

            print(f" => ✅ SELL order successfully filled! Order ID: {order['id']}")

            # Save to history
            signal_id = state.get("signal_id")
            db.save_trade(order, signal_id)



            return {
                "action_taken": "SELL",
                "action_amount": actual_size,
                "action_message": f"Sell successful: {order['id']}",
            }

    except Exception as e:
        print(f" ❌ Order Execution Error: {e}")
        return {"action_taken": "SKIP", "action_message": f"Order execution error: {e}"}


def build_execution_graph():
    builder = StateGraph(ExecutionState)

    builder.add_node("Read_Brain_Signal", read_brain_signal)
    builder.add_node("Read_Binance_Data", read_binance_data)
    builder.add_node("Check_Constraints", check_constraints)
    builder.add_node("Execute_Trade", execute_trade)

    builder.add_edge(START, "Read_Brain_Signal")
    builder.add_edge("Read_Brain_Signal", "Read_Binance_Data")
    builder.add_edge("Read_Binance_Data", "Check_Constraints")
    builder.add_edge("Check_Constraints", "Execute_Trade")
    builder.add_edge("Execute_Trade", END)

    return builder.compile()


graph = build_execution_graph()


if __name__ == "__main__":
    import asyncio

    print("\n" + "=" * 60)
    print("🚀 STARTING BINANCE TRADING GRAPH (NO STOP LOSS)")
    print("=" * 60 + "\n")

    initial_state = {}

    async def run_scenario(state):
        async for chunk in graph.astream(state):
            pass

    asyncio.run(run_scenario(initial_state))

    print("\n" + "=" * 60)
    print("✅ COMPLETED REAL TESTNET EXECUTION!")
    print("=" * 60 + "\n")
