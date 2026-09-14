from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.app_user import AppUser
from app.schemas.auth import LoginRequest, TokenResponse, UserPublic
from app.services.app_auth import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    if not user.id:
        return UserPublic(id=0, email=user.email, role=user.role, is_active=True)
    row = db.query(AppUser).filter(AppUser.id == user.id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return UserPublic.model_validate(row)
