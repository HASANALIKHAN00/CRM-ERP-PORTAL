"""
Portfolio Demo Mode switch and its fictional user directory.

Deliberately free of any `models`/`database` imports so `database.py` can
read DEMO_MODE while deciding which engine to build, without a circular
import. The actual dataset lives in demo_data.py.

Nothing here reads ERPNext or Postgres -- when DEMO_MODE is on, the whole
app runs against a self-contained in-memory dataset instead.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


DEMO_MODE = _flag("DEMO_MODE")

# Shared sign-in password for every demo account. Not a secret: demo mode
# serves fictional data only, and this never unlocks live ERPNext or the
# production database.
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo1234")

DEMO_EMAIL_DOMAIN = "demo.example"  # RFC 2606 reserved -- can never resolve

ADMIN_DEPARTMENT = "Sales - BT"

# (full_name, department) -- emails and employee ids are derived below so
# there is exactly one place to edit the roster.
_ROSTER = [
    ("Ahmed Khan", "Sales - BT", "admin"),
    ("Sara Malik", "Sales - BT", "sales_user"),
    ("Fatima Noor", "Sales - BT", "sales_user"),
    ("Hamza Ali", "Sales - BT", "sales_user"),
    ("Zainab Iqbal", "Sales - BT", "sales_user"),
    ("Ayesha Rahman", "Customer Success - BT", "sales_user"),
    ("Bilal Ahmed", "Customer Success - BT", "sales_user"),
    ("Usman Tariq", "Business Development - BT", "sales_user"),
    ("Hira Shah", "Business Development - BT", "sales_user"),
    ("Omar Farooq", "Technical Support - BT", "sales_user"),
]


def _email_for(full_name: str) -> str:
    return f"{full_name.lower().replace(' ', '.')}@{DEMO_EMAIL_DOMAIN}"


DEMO_USERS = [
    {
        "employee_id": f"HR-EMP-{index:04d}",
        "full_name": full_name,
        "email": _email_for(full_name),
        "department": department,
        "role": role,
    }
    for index, (full_name, department, role) in enumerate(_ROSTER, start=1)
]

DEMO_USERS_BY_EMAIL = {u["email"]: u for u in DEMO_USERS}

# The account the demo is meant to be shown from -- admin sees every
# company-wide report instead of the sales_user-scoped subset.
DEMO_ADMIN_EMAIL = DEMO_USERS[0]["email"]


def verify_demo_login(email: str, password: str) -> dict:
    """ERPNext-free stand-in for erpnext_client.verify_login."""
    user = DEMO_USERS_BY_EMAIL.get((email or "").strip().lower())
    if not user or password != DEMO_PASSWORD:
        return {"success": False}
    return {"success": True, "full_name": user["full_name"], "role": user["role"]}
