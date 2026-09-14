from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_admin
from app.db.session import get_db
from app.models.app_user import AppUser
from app.schemas.auth import UserCreate, UserPublic, UserUpdate
from app.services.app_auth import hash_password, normalize_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserPublic])
def list_users(_admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)) -> list[UserPublic]:
    rows = db.query(AppUser).order_by(AppUser.email).all()
    return [UserPublic.model_validate(r) for r in rows]


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserPublic:
    email = normalize_email(payload.email)
    if db.query(AppUser).filter(AppUser.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    row = AppUser(
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserPublic.model_validate(row)


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserPublic:
    row = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.is_active is False and row.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    if payload.is_active is False and row.role == "admin":
        other_admins = (
            db.query(AppUser)
            .filter(AppUser.role == "admin", AppUser.is_active.is_(True), AppUser.id != row.id)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the last admin")

    if payload.password is not None:
        row.password_hash = hash_password(payload.password)
    if payload.is_active is not None:
        row.is_active = payload.is_active

    db.commit()
    db.refresh(row)
    return UserPublic.model_validate(row)
