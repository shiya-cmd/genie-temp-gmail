import requests

SMSBOWER_API_KEY = "YOUR_API_KEY"

def get_temp_mail(service="kt", domain="gmail.com"):
    r = requests.get(
        "https://smsbower.online/api/mail/getActivation",
        params={
            "api_key": SMSBOWER_API_KEY,
            "service": service,
            "domain": domain,
            "alias": 1
        },
        timeout=10,
    )
    data = r.json()
    if data.get("status") != 1:
        return None, None

    return data["mail"], data["mailId"]

def get_mail_code(mail_id):
    r = requests.get(
        "https://smsbower.online/api/mail/getCode",
        params={"api_key": SMSBOWER_API_KEY, "mailId": mail_id},
        timeout=10,
    )
    data = r.json()
    return data.get("code") if data.get("status") == 1 else None
