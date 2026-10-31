from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    token = authenticate(payload.username, payload.password)
    return LoginResponse(token=token)
