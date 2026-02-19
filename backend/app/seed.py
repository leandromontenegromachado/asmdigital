from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import User


def seed_admin(db: Session) -> None:
    user = db.query(User).filter(User.email == settings.admin_email).first()
    if user:
        return
    admin = User(
        name="Admin",
        email=settings.admin_email,
        password_hash=get_password_hash(settings.admin_password),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        seed_admin(db)
