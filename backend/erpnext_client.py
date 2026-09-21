import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

ERPNEXT_URL = os.getenv("ERPNEXT_URL")
API_KEY = os.getenv("ERPNEXT_API_KEY")
API_SECRET = os.getenv("ERPNEXT_API_SECRET")

HEADERS = {
    "Authorization": f"token {API_KEY}:{API_SECRET}",
    "Content-Type": "application/json",
}


def get_records(doctype: str, filters: list = None, fields: list = None, page_size: int = 500, parent: str = None):
    """
    Fetch ALL records for a given DocType via Frappe's REST API,
    paginating automatically. page_size is the per-request page size,
    not a cap on total results — the function loops until a page
    comes back smaller than page_size, meaning no more records remain.
    """
    all_records = []
    start = 0

    while True:
        params = {"limit_page_length": page_size, "limit_start": start}
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)
        if parent:
            params["parent"] = parent

        response = requests.get(
            f"{ERPNEXT_URL}/api/resource/{doctype}",
            headers=HEADERS,
            params=params,
        )

        if response.status_code >= 400:
            print(f"ERPNext API error {response.status_code} for {doctype}:")
            print(response.text[:2000])

        response.raise_for_status()
        page = response.json().get("data", [])
        all_records.extend(page)

        if len(page) < page_size:
            break  # last page reached
        start += page_size

    return all_records


def verify_login(email: str, password: str) -> dict:
    """
    Checks real credentials against ERPNext's own login endpoint.
    Never stores the password anywhere — checked once per attempt, then discarded.
    """
    normalized_email = (email or "").strip().lower()

    response = requests.post(
        f"{ERPNEXT_URL}/api/method/login",
        data={"usr": normalized_email, "pwd": password},
        timeout=10,
    )

    if response.status_code >= 400:
        return {"success": False}

    try:
        body = response.json()
    except ValueError:
        return {"success": False}

    message = body.get("message")
    if isinstance(message, str):
        if message.strip().lower() == "logged in":
            return {"success": True, "full_name": body.get("full_name") or normalized_email}
    if body.get("success") is True:
        return {"success": True, "full_name": body.get("full_name") or normalized_email}
    if isinstance(message, dict) and (message.get("full_name") or message.get("user")):
        return {"success": True, "full_name": message.get("full_name") or body.get("full_name") or normalized_email}

    return {"success": False}


def get_user_roles(email: str) -> list:
    """
    Fetches the full User document (not the generic list endpoint, which
    omits the roles child table) and returns real ERPNext role names
    assigned to this user, via the service API key.
    """
    response = requests.get(f"{ERPNEXT_URL}/api/resource/User/{email}", headers=HEADERS)
    response.raise_for_status()
    return [r["role"] for r in response.json().get("data", {}).get("roles", [])]
