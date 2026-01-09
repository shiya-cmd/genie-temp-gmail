import os, time, random, string, requests, segno
from flask import Flask, render_template, request, redirect, session, jsonify
import requests
from flask import abort,url_for
from otp_worker import start_otp_worker
from wallet import add_wallet_history

PAYTM_WORKER_URL = "https://paytm.udayscriptsx.workers.dev/"
PAYTM_MID = "OtWRkM00455638249469"

app = Flask(__name__)
app.secret_key = "super-secret-key"
from datetime import datetime
@app.template_filter("datetimeformat")
def datetimeformat(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d %b %Y %H:%M")
    except Exception:
        return "-"

# ================= CONFIG =================
FIREBASE_URL = "https://temp-f2fe1-default-rtdb.asia-southeast1.firebasedatabase.app"
SMSBOWER_API_KEY = "q3xSZbaPVpaZW5zsI4tzea7s0RlLfun3"

UPI_VPA = "paytmqr2810050501013202t473pymf@paytm"
MERCHANT_NAME = "OORPAY"

USD_TO_INR = 90.0          # update if needed
PROVIDER_MARKUP = 1.20    # +20% (already included sometimes, keep configurable)
YOUR_MARGIN_INR = 5       # your profit per mail
ALLOWED_DOMAINS = {"gmail.com", "mailnestpro.com"}  # optional filter

OTP_TIMEOUT_SECONDS = 5 * 60  # 20 minutes
# =========================================


# ================= FIREBASE =================
def fb_get(path):
    r = requests.get(f"{FIREBASE_URL}/{path}.json")
    return r.json() if r.ok else None

def fb_set(path, data):
    requests.put(f"{FIREBASE_URL}/{path}.json", json=data)

def fb_update(path, data):
    requests.patch(f"{FIREBASE_URL}/{path}.json", json=data)
# ===========================================


# ================= AUTH =================
def gen_user_id():
    return "USR" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def gen_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))

def get_user():
    uid = session.get("user")
    if not uid:
        return None, None
    try:
        user = fb_get(f"users/{uid}")
    except Exception:
        # network error → treat as still logged in
        return uid, None
    if not user:
        # user truly deleted from DB
        session.clear()
        return None, None

    return uid, user
# =======================================


# ================= PAYMENT =================
def gen_order_id():
    return "ORD" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_qr(order_id, amount):
    upi = f"upi://pay?pa={UPI_VPA}&pn={MERCHANT_NAME}&am={amount}&cu=INR&&tn={order_id}&tr={order_id}&tid={order_id}"
    path = f"static/{order_id}.png"
    segno.make(upi).save(path, scale=8)
    return path

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

# ==========================================


# ================= SMSBOWER =================
def get_mail_services():
    r = requests.get(
        "https://smsbower.online/stubs/handler_api.php",
        params={
            "api_key": SMSBOWER_API_KEY,
            "action": "getMailServicesList",
        },
        timeout=10,
    )
    data = r.json()
    return data.get("services", []) if data.get("status") == "success" else []

def get_mail_prices():
    try:
        r = requests.get(
            "https://smsbower.online/api/mail/getPrices",
            params={"api_key": SMSBOWER_API_KEY},
            timeout=15,
        )

        data = r.json()

        # CASE 1: Proper object response
        if isinstance(data, dict):
            if data.get("status") == 1:
                return data.get("prices", [])
            return []

        # CASE 2: API returned list directly
        if isinstance(data, list):
            return data

        return []

    except Exception as e:
        print("Price fetch error:", e)
        return []



def build_catalog():
    services = get_mail_services()
    prices = get_mail_prices()

    # Build price lookup: service -> cheapest option
    price_map = {}

    for p in prices:
        service = p.get("service")
        domain = p.get("domain")
        price_usd = float(p.get("price", 0))

        if not service or price_usd <= 0:
            continue

        if ALLOWED_DOMAINS and domain not in ALLOWED_DOMAINS:
            continue

        if service not in price_map or price_usd < price_map[service]["usd"]:
            price_map[service] = {
                "usd": price_usd,
                "domain": domain,
            }

    catalog = {}

    for s in services:
        code = s["code"]
        name = s["name"]

        if code not in price_map:
            continue  # no price → skip

        usd = price_map[code]["usd"]
        domain = price_map[code]["domain"]

        # 💰 Final INR price
        inr = usd * USD_TO_INR
        inr *= PROVIDER_MARKUP
        inr += YOUR_MARGIN_INR

        CATEGORIES = {
            "ig": "social", "fb": "social", "tg": "social", "tw": "social",
            "ds": "social", "fu": "social",

            "git": "dev", "aws": "dev", "crsr": "dev", "ser": "dev",

            "am": "ecom", "ebay_kl": "ecom", "wr": "ecom", "lc": "ecom",
        }
        POPULAR = {"gg", "fb", "ig", "tw", "am", "aws", "git"}

        catalog[code] = {
            "name": name,
            "price": round(inr),
            "popular": code in POPULAR,
            "category": CATEGORIES.get(code, "other"),
        }


    return catalog





def get_temp_mail(service):
    r = requests.get(
        "https://smsbower.online/api/mail/getActivation",
        params={
            "api_key": SMSBOWER_API_KEY,
            "service": service,
            "domain": "gmail.com"
        },
    )
    d = r.json()
    return (d["mail"], d["mailId"]) if d.get("status") == 1 else (None, None)

def get_mail_code(mail_id):
    r = requests.get(
        "https://smsbower.online/api/mail/getCode",
        params={"api_key": SMSBOWER_API_KEY, "mailId": mail_id},
    )
    d = r.json()
    return d.get("code") if d.get("status") == 1 else None

def smsbower_cancel_mail(mail_id: int) -> bool:
    """
    Cancel temp mail activation
    status = 2 (Cancel)
    """
    try:
        r = requests.get(
            "https://smsbower.online/api/mail/setStatus",
            params={
                "api_key": SMSBOWER_API_KEY,
                "id": mail_id,
                "status": 2,
            },
            timeout=10,
        )

        data = r.json()
        return isinstance(data, dict) and data.get("status") == 1

    except Exception:
        return False

import threading
import time
def otp_worker(order_id):
    """
    Background worker:
    - Polls SMSBower
    - Saves OTP in Firebase
    - Handles timeout + cancel
    """

    while True:
        print('Fetching OTP...')
        order = fb_get(f"orders/{order_id}")
        if not order:
            return

        # Stop if already finished
        if order.get("status") in ("SUCCESS", "TIMEOUT"):
            return

        # Timeout (20 minutes)
        if time.time() > order["expires_at"]:
            smsbower_cancel_mail(order["mail_id"])
            fb_update(f"orders/{order_id}", {
                "status": "TIMEOUT"
            })
            return

        # Fetch OTP from SMSBower
        code = get_mail_code(order["mail_id"])
        print('Fetched OTP:', code)
        if code:
            fb_update(f"orders/{order_id}", {
                "status": "SUCCESS",
                "otp": code
            })
            return

        time.sleep(3)  # poll every 10 seconds

import time
import random
import string

def add_wallet_history(tx_type, amount, order_id="", note=""):
    uid, _ = get_user()
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

# ===========================================


# ================= ROUTES =================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup")
def signup():
    if "user" in session:
        return render_template("error.html", message="User already logged in")
    uid, pwd = gen_user_id(), gen_password()
    fb_set(f"users/{uid}", {"password": pwd, "wallet": 0, "created": time.time()})
    session["user"] = uid
    return render_template("signup.html", uid=uid, pwd=pwd)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid, pwd = request.form["uid"], request.form["pwd"]
        user = fb_get(f"users/{uid}")
        if user and user["password"] == pwd:
            session["user"] = uid
            return redirect("/dashboard")
        return "Invalid login"
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    uid, user = get_user()
    if not uid:
        return redirect("/login")

    session["wallet"] = user.get("wallet", 0)
    return render_template("dashboard.html")


@app.route("/services")
def services():
    uid, user = get_user()
    session["wallet"] = user.get("wallet", 0)

    if not uid:
        return redirect("/login")
    wallet = user["wallet"]
    return render_template("services.html", services=build_catalog(), wallet=wallet)

@app.route("/temp", methods=["POST"])
def temp_mail():
    uid, user = get_user()
    if not uid:
        return redirect("/login")

    service = request.form.get("service")
    if not service:
        abort(400)

    catalog = build_catalog()
    if service not in catalog:
        abort(400)

    price = catalog[service]["price"]

    # Wallet check
    if user["wallet"] < price:
        return render_template("error.html", message="Insufficient wallet balance")

    # Deduct wallet
    user["wallet"] -= price
    fb_set(f"users/{uid}", user)

    # Create order
    order_id = gen_order_id()
    now = int(time.time())

    # Get temp mail
    try:
        mail, mail_id = get_temp_mail(service)
    except Exception:
        fb_update(f"orders/{order_id}", {"status": "FAILED"})
        return render_template("error.html", message="Failed to get mail Try Again")
    
    if not mail or not mail_id:
        fb_update(f"orders/{order_id}", {"status": "FAILED"})
        return render_template("error.html", message="Failed to get mail Try Again")

    fb_set(f"orders/{order_id}", {
        "user": uid,
        "service": service,
        "price": price,
        "status": "PENDING",
        "wallet_deducted": 'true',
        "refunded": 'false',
        "created_at": now,
        "expires_at": now + OTP_TIMEOUT_SECONDS,
    })
    fb_update(f"orders/{order_id}", {
        "mail": mail,
        "mail_id": mail_id,
        "status": "WAITING_OTP"
    })
    add_wallet_history(
        "DEDUCT",
        price,
        order_id,
        f"Temp mail for {service}"
    )

    # 🔥 Start background worker
    threading.Thread(
        target=start_otp_worker,
        args=(order_id,),
        daemon=True
    ).start()
    return redirect(url_for("otp_page", order_id=order_id))

@app.route("/otp/<order_id>")
def otp_page(order_id):
    order = fb_get(f"orders/{order_id}")
    if not order:
        abort(404)
    uid, user = get_user()
    session["wallet"] = user.get("wallet", 0)

    return render_template(
        "otp.html",
        order_id=order_id,
        mail=order.get("mail"),
        expires_at=order.get("expires_at")
    )

@app.route("/api/otp/<order_id>")
def api_otp(order_id):
    order = fb_get(f"orders/{order_id}")
    if not order:
        return jsonify({"status": "invalid"})

    if order["status"] == "SUCCESS":
        return jsonify({"otp": order.get("otp")})

    if order["status"] == "TIMEOUT":
        return jsonify({"status": "timeout"})

    return jsonify({"status": "waiting"})


@app.route("/api/mail/<mail_id>")
def mail_code(mail_id):
    return jsonify({"code": get_mail_code(mail_id)})

@app.route("/recharge", methods=["GET"])
def recharge():
    uid, _ = get_user()
    if not uid:
        return redirect("/login")
    uid, user = get_user()
    session["wallet"] = user.get("wallet", 0)
    return render_template("recharge_amount.html")

@app.route("/recharge/create", methods=["POST"])
def recharge_create():
    uid, user = get_user()
    session["wallet"] = user.get("wallet", 0)
    if not uid:
        return redirect("/login")

    try:
        amount = int(request.form["amount"])
        if amount < 10:
            return render_template("error.html", message="Minimum recharge is ₹10")
    except ValueError:
        return render_template("error.html", message="Invalid amount")

    order_id = gen_order_id()

    fb_set(f"recharges/{order_id}", {
        "user": uid,
        "amount": amount,
        "status": "PENDING",
        "created_at": int(time.time())
    })

    qr = generate_qr(order_id, amount)

    return render_template(
        "recharge_qr.html",
        order_id=order_id,
        qr=qr,
        amount=amount
    )

@app.route("/api/recharge/status/<order_id>")
def recharge_status(order_id):
    db_order = fb_get(f"recharges/{order_id}")

    if not db_order:
        return jsonify({"status": "invalid"})

    # Already credited
    if db_order["status"] == "SUCCESS":
        return jsonify({"status": "success"})

    # Check payment
    if check_payment(order_id):
        uid = db_order["user"]
        user = fb_get(f"users/{uid}")

        if not user:
            return jsonify({"status": "failed"})

        # Credit wallet ONCE
        fb_update(f"users/{uid}", {
            "wallet": user.get("wallet", 0) + db_order["amount"]
        })

        fb_update(f"recharges/{order_id}", {
            "status": "SUCCESS"
        })
        add_wallet_history(
            "RECHARGE",
            db_order["amount"],
            order_id,
            "Wallet recharge"
        )


        return jsonify({"status": "success"})

    return jsonify({"status": "pending"})

@app.route("/api/wallet-balance")
def api_wallet_balance():
    uid, user = get_user()
    if not uid:
        return jsonify({"balance": None})

    return jsonify({
        "balance": user.get("wallet", 0)
    })


@app.route("/wallet")
def wallet():
    uid, user = get_user()
    if not uid:
        return redirect("/login")

    history = fb_get(f"wallet_history/{uid}") or {}
    history_list = list(history.values())

    history_list.sort(key=lambda x: x["time"], reverse=True)

    return render_template(
        "wallet.html",
        balance=user.get("wallet", 0),
        history=history_list
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
# =========================================


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)))
