from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas import LoginRequest, TokenResponse, UserResponse
from ..security import create_access_token, get_current_user, verify_admin_credentials


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not verify_admin_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return TokenResponse(access_token=create_access_token(payload.username))


@router.get("/me", response_model=UserResponse)
def me(username: str = Depends(get_current_user)) -> UserResponse:
    return UserResponse(username=username)

