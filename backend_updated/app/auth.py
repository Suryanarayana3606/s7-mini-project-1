"""
app/auth.py

Authentication. Streamlit's original login() just set a boolean in
st.session_state, which only works because Streamlit keeps server-side
session state per browser tab automatically. A stateless REST API needs
its own mechanism, so this issues a short-lived JWT on successful login
that the React app stores and sends as a Bearer token on every request.

Credentials are still the same demo admin/admin123 pair as the original
(configurable via env vars) — this is a like-for-like port of the
original app's auth model, not a security upgrade. See the README for
notes on what to change before any real deployment.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import AUTH_USERNAME, AUTH_PASSWORD, JWT_SECRET

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12

_security = HTTPBearer(auto_error=False)


def authenticate(username: str, password: str) -> str:
    if username != AUTH_USERNAME or password != AUTH_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
