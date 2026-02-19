from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models import User
from app.schemas.users import UserCreate, UserOut, UserPasswordReset, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
    q: str | None = Query(None),
):
    query = db.query(User)
    if q:
        ilike = f"%{q}%"
        query = query.filter((User.name.ilike(ilike)) | (User.email.ilike(ilike)))
    return query.order_by(User.id.asc()).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "email" in data:
        email_exists = db.query(User).filter(User.email == data["email"], User.id != user_id).first()
        if email_exists:
            raise HTTPException(status_code=400, detail="Email already exists")
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int,
    payload: UserPasswordReset,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = get_password_hash(payload.password)
    db.commit()
    db.refresh(user)
    return user
