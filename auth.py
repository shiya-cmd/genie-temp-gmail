import random, string, time
from flask import session
from firebase import fb_get, fb_set

def gen_user_id():
    return "USR" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def gen_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))

def create_user():
    user_id = gen_user_id()
    password = gen_password()

    fb_set(f"users/{user_id}", {
        "password": password,
        "wallet": 0,
        "created_at": int(time.time())
    })

    return user_id, password

def get_logged_user():
    user_id = session.get("user")
    if not user_id:
        return None, None

    user = fb_get(f"users/{user_id}")
    if not user:
        session.clear()
        return None, None

    return user_id, user

ADMIN_USERS = {"USRADMIN1", "USRADMIN2"}  # your admin user IDs

def is_admin(user_id):
    return user_id in ADMIN_USERS
