import asyncio
import time
import aiohttp

# ================= CONFIG =================

FIREBASE_URL = "https://temp-f2fe1-default-rtdb.asia-southeast1.firebasedatabase.app"
SMSBOWER_API_KEY = "q3xSZbaPVpaZW5zsI4tzea7s0RlLfun3"

OTP_TIMEOUT_SECONDS = 5 * 60  # 20 minutes
OTP_POLL_INTERVAL = 6          # seconds

# =========================================


# ================= FIREBASE ASYNC CLIENT =================

class FirebaseAsync:
    def __init__(self):
        self.session = None

    async def start(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


    async def get(self, path: str):
        try:
            async with self.session.get(f"{FIREBASE_URL}/{path}.json") as r:
                if r.status == 200:
                    return await r.json()
        except Exception as e:
            print("[Firebase GET]", e)
        return None

    async def set(self, path: str, data: dict):
        try:
            async with self.session.put(
                f"{FIREBASE_URL}/{path}.json", json=data
            ):
                pass
        except Exception as e:
            print("[Firebase SET]", e)

    async def update(self, path: str, data: dict):
        try:
            async with self.session.patch(
                f"{FIREBASE_URL}/{path}.json", json=data
            ):
                pass
        except Exception as e:
            print("[Firebase UPDATE]", e)

# =========================================================


# ================= SMSBOWER MAIL API =================

async def get_mail_code(session: aiohttp.ClientSession, mail_id: str):
    """
    Fetch OTP code for temp mail
    """
    try:
        async with session.get(
            "https://smsbower.online/api/mail/getCode",
            params={
                "api_key": SMSBOWER_API_KEY,
                "mailId": mail_id,
            },
        ) as r:
            data = await r.json()
            if isinstance(data, dict) and data.get("status") == 1:
                return data.get("code")
    except Exception as e:
        print("[SMSBower getCode]", e)

    return None


async def cancel_mail(session: aiohttp.ClientSession, mail_id: str):
    """
    Cancel mail activation
    status=2 → cancel
    """
    try:
        await session.get(
            "https://smsbower.online/api/mail/setStatus",
            params={
                "api_key": SMSBOWER_API_KEY,
                "id": mail_id,
                "status": 2,
            },
        )
    except Exception as e:
        print("[SMSBower cancel]", e)

import time
import random
import string
from firebase import fb_set
def add_wallet_history(uid, tx_type, amount, order_id="", note=""):

    if not uid:
        return  # silently fail if no session

    tx_id = "TX" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

    fb_set(f"wallet_history/{uid}/{tx_id}", {
        "type": tx_type,              # RECHARGE | DEDUCT | REFUND
        "amount": round(float(amount), 2),
        "order_id": order_id,
        "note": note,
        "time": int(time.time())
    })


async def refund_wallet(fb, user_id: str, amount: float, order_id: str):
    user = await fb.get(f"users/{user_id}")
    if not user:
        return

    balance = float(user.get("wallet", 0))
    new_balance = balance + amount

    await fb.update(f"users/{user_id}", {
        "wallet": round(new_balance, 2)
    })

    # 💾 Refund log
    await fb.update(f"refunds/{order_id}", {
        "user_id": user_id,
        "amount": amount,
        "time": time.time()
    })
    add_wallet_history(
        user_id,
        "REFUND",
        amount,
        order_id,
        "OTP timeout refund"
    )

    print(f"[REFUND] ₹{amount} refunded to {user_id}")

# =====================================================


# ================= OTP BACKGROUND WORKER =================

async def otp_worker(order_id: str):
    print(f"[OTP WORKER STARTED] {order_id}")

    fb = FirebaseAsync()
    await fb.start()

    timeout = aiohttp.ClientTimeout(total=15)
    http = aiohttp.ClientSession(timeout=timeout)

    try:
        while True:
            order = await fb.get(f"orders/{order_id}")

            if not order:
                print("[OTP WORKER] Order missing, exit")
                return

            status = order.get("status", "PENDING")
            mail_id = order.get("mail_id")
            created_at = order.get("created_at")

            if not mail_id or not created_at:
                print("[OTP WORKER] Invalid order data")
                return

            # ⏳ TIMEOUT CHECK
            # ⏳ TIMEOUT CHECK
            if time.time() > order["expires_at"]:

                await cancel_mail(http, order["mail_id"])

                # 💸 WALLET REFUND
                if (
                    order.get("wallet_deducted")
                    and not order.get("refunded")
                    and order.get("status") != "SUCCESS"
                ):
                    await refund_wallet(
                        fb,
                        order["user_id"],
                        order["price"],
                        order_id
                    )

                    await fb.update(f"orders/{order_id}", {
                        "refunded": True
                    })

                await fb.update(f"orders/{order_id}", {
                    "status": "TIMEOUT",
                    "expired_at": time.time()
                })

                print("[OTP WORKER] Timeout → refunded")
                return


            # ✅ ALREADY DONE
            if status == "SUCCESS":
                print("[OTP WORKER] Already completed")
                return

            # 📩 FETCH OTP
            code = await get_mail_code(http, mail_id)
            if code:
                await fb.update(f"orders/{order_id}", {
                    "status": "SUCCESS",
                    "otp": code,
                    "received_at": time.time(),
                })
                print("[OTP WORKER] OTP received")
                return

            await asyncio.sleep(OTP_POLL_INTERVAL)

    except Exception as e:
        print("[OTP WORKER ERROR]", e)

    finally:
        # ✅ GUARANTEED CLEANUP
        await http.close()
        await fb.close()
        print("[OTP WORKER CLOSED]")


# ========================================================


# ================= THREAD ENTRY (FOR FLASK) =================

def start_otp_worker(order_id: str):
    """
    Use this from Flask:
    threading.Thread(target=start_otp_worker, args=(order_id,), daemon=True).start()
    """
    asyncio.run(otp_worker(order_id))

# ============================================================
