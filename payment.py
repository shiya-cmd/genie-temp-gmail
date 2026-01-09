import segno, random, string, time

UPI_VPA = "paytmqr2810050501013202t473pymf@paytm"
MERCHANT_NAME = "OORPAY"

def generate_order_id(prefix="RCG"):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_qr(order_id, amount):
    upi = (
        f"upi://pay?pa={UPI_VPA}&pn={MERCHANT_NAME}"
        f"&am={amount}&cu=INR&tn={order_id}&tr={order_id}&tid={order_id}"
    )

    path = f"static/qr/{order_id}.png"
    segno.make(upi).save(path, scale=8)
    return path

import requests
PAYTM_WORKER_URL = "https://paytm.udayscriptsx.workers.dev/"
PAYTM_MID = "OtWRkM00455638249469"
def check_payment(order_id):
    try:
        r = requests.get(
            PAYTM_WORKER_URL,
            params={"mid": PAYTM_MID, "id": order_id},
            timeout=10,
        )

        if r.status_code != 200:
            return False

        try:
            data = r.json()
        except ValueError:
            return False

        return isinstance(data, dict) and data.get("STATUS") == "TXN_SUCCESS"

    except requests.RequestException:
        return False

