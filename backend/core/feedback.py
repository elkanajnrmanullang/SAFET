def store_trade(trade_context, result):
    trade_context["result"] = result
    trade_context["timestamp"] = time.time()
    # simpan ke DB / JSON
