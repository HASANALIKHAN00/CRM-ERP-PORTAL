import os
import time
import jwt
from fastapi import Cookie, HTTPException
from dotenv import load_dotenv
import erpnext_client

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours default

ADMIN_ROLE_NAME = "System Manager"
COOKIE_NAME = "session_token"


def resolve_role(email: str) -> str:
    """
    Maps real ERPNext roles to our two-tier model, per Hassan's spec:
    System Manager -> admin (full access), everything else -> sales_user
    (scoped to their own customers/activities).
    """
    roles = erpnext_client.get_user_roles(email)
    return "admin" if ADMIN_ROLE_NAME in roles else "sales_user"


def create_access_token(email: str, role: str, full_name: str) -> str:
    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: JWT_SECRET_KEY not set")
    payload = {
        "sub": email,
        "role": role,
        "full_name": full_name,
        "exp": time.time() + JWT_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(session_token: str = Cookie(None, alias=COOKIE_NAME)) -> dict:
    """
    Dependency for protected endpoints. Reads the JWT from the httpOnly
    session cookie (set by /auth/login) rather than an Authorization header.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in")

    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: JWT_SECRET_KEY not set")

    try:
        payload = jwt.decode(session_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    return {"email": payload["sub"], "role": payload["role"], "full_name": payload.get("full_name")}
