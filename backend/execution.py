def execute_trade(client, symbol, decision):
    if decision["status"] != "EXECUTE":
        return decision

    side = "BUY" if decision["direction"] == "LONG" else "SELL"

    client.futures_change_margin_type(
        symbol=symbol,
        marginType="ISOLATED"
    )

    client.futures_create_order(
        symbol=symbol,
        side=side,
        type="MARKET",
        quantity=decision["risk"]["position_size"]
    )

    return {"status": "ORDER_SENT", "details": decision}
