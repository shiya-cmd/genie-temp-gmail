import json, os, time, random, string

DB_FILE = "db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "recharges": {}}

    try:
        with open(DB_FILE, "r") as f:
            data = f.read().strip()
            if not data:
                return {"users": {}, "recharges": {}}
            return json.loads(data)
    except (json.JSONDecodeError, IOError):
        # Backup corrupted file (optional but recommended)
        try:
            os.rename(DB_FILE, DB_FILE + ".broken")
        except Exception:
            pass

        return {"users": {}, "recharges": {}}


def save_db(db):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp, DB_FILE)


def gen_user_id():
    return "USR" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def gen_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=8))
