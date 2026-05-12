from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

security = HTTPBearer()
ADMIN_ROLES = {"admin", "gerente"}
VALID_USER_ROLES = {"admin", "gerente", "funcionario", "viewer"}


def normalize_role(role: str | None) -> str:
    normalized = (role or "funcionario").strip().lower()
    return "funcionario" if normalized == "viewer" else normalized


def has_admin_access(user: User) -> bool:
    return normalize_role(user.role) in ADMIN_ROLES


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(creds.credentials)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not has_admin_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or manager access required")
    return current_user
