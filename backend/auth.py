from fastapi import Cookie, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi import Form
from jose import jwt, JWTError
import datetime
import os
import bcrypt
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY")
PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
USERNAME = "admin"

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_token(username: str) -> str:
    return jwt.encode(
        {"sub": username, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)},
        SECRET_KEY,
        algorithm="HS256"
    )

def authenticate(access_token: str = Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    try:
        payload = jwt.decode(access_token.replace("Bearer ", ""), SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=307, headers={"Location": "/login"})

def verify_ws_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        jwt.decode(token.replace("Bearer ", ""), SECRET_KEY, algorithms=["HS256"])
        return True
    except JWTError:
        return False