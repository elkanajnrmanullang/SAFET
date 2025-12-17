import os
import math
from typing import Dict, Any


SIMULATE = os.getenv("SIMULATE_TRADES", "1") == "1"


def execute_trade(client, symbol: str, decision: Dict[str, Any]) -> Dict[str, Any]:
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

        # Real execution 
        if hasattr(client, "create_order"):
            order = client.create_order(
                symbol=symbol.replace("/", ""),
                type="MARKET",
                side=side,
                amount=qty
            )
            return {"status": "ORDER_SENT", "details": order}

        if hasattr(client, "futures_create_order"):
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

        return {"status": "NO_ACTION", "reason": "unsupported_client", "details": decision}

    except Exception as e:
        return {"status": "ERROR", "error": str(e), "details": decision}
