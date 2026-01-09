import time

async def add_wallet_history(fb, user_id, tx_type, amount, order_id, note=""):
    tx_id = f"TX{int(time.time() * 1000)}"

    await fb.update(f"wallet_history/{user_id}/{tx_id}", {
        "type": tx_type,
        "amount": round(amount, 2),
        "order_id": order_id,
        "time": time.time(),
        "note": note
    })
