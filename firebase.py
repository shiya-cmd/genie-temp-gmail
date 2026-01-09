import requests

FIREBASE_URL = "https://temp-f2fe1-default-rtdb.asia-southeast1.firebasedatabase.app"

def fb_get(path):
    r = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=10)
    return r.json() if r.status_code == 200 else None

def fb_set(path, data):
    requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)

def fb_update(path, data):
    requests.patch(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
