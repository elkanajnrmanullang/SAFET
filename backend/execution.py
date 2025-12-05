"""
Execution helper for placing orders on exchange.
Wrapper supports:
- real Binance client (ccxt or python-binance-like clients)
- simulation mode controlled by env SIMULATE_TRADES=1
"""

import os
import math
from typing import Dict, Any


SIMULATE = os.getenv("SIMULATE_TRADES", "1") == "1"


def execute_trade(client, symbol: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    client: exchange client supporting similar methods as python-binance or ccxt.
    decision: dict produced by ai_engine.final_decision

    Returns:
      {"status": "ORDER_SENT"|"SIMULATED"|"NO_ACTION", "details": {...}}
    """
    if not decision or decision.get("status") != "EXECUTE":
        return {"status": "NO_ACTION", "details": decision}

    try:
        direction = decision.get("direction")
        side = "BUY" if direction and direction.upper() == "LONG" else "SELL"
        risk = decision.get("risk", {})
        qty = risk.get("position_size")

        # sanity checks
        if not qty or qty <= 0:
            return {"status": "NO_ACTION", "reason": "position_size_invalid", "details": decision}

        # Simulation mode
        if SIMULATE:
            return {
                "status": "SIMULATED",
                "details": {
                    "symbol": symbol,
                    "side": side,
                    "quantity": qty,
                    "sl": risk.get("stop_loss"),
                    "tp": risk.get("take_profit"),
                    "note": "SIMULATION MODE - no real order placed"
                }
            }

        # Real execution (example for python-binance-like client)
        # try ccxt style first (unified)
        if hasattr(client, "create_order"):
            order = client.create_order(
                symbol=symbol.replace("/", ""),
                type="MARKET",
                side=side,
                amount=qty
            )
            return {"status": "ORDER_SENT", "details": order}

        # python-binance style (futures_create_order)
        if hasattr(client, "futures_create_order"):
            # ensure margin type isolated (best-effort)
            try:
                if hasattr(client, "futures_change_margin_type"):
                    client.futures_change_margin_type(symbol=symbol.replace("/", ""), marginType="ISOLATED")
            except Exception:
                pass

            order = client.futures_create_order(
                symbol=symbol.replace("/", ""),
                side=side,
                type="MARKET",
                quantity=qty
            )
            return {"status": "ORDER_SENT", "details": order}

        # unsupported client
        return {"status": "NO_ACTION", "reason": "unsupported_client", "details": decision}

    except Exception as e:
        return {"status": "ERROR", "error": str(e), "details": decision}
