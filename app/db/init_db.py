import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.user import User
from app.models.target import Target

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db(db: Session) -> None:
    # Create tables directly
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

    # Create an admin user if not exists
    user = db.query(User).filter(User.email == "admin@securelens.local").first()
    if not user:
        # In a real app, hash the password
        user = User(
            email="admin@securelens.local",
            hashed_password="hashed_admin_password", # fake hash
            is_superuser=True
        )
        db.add(user)
        logger.info("Admin user created.")

    # Seed Lab Mode targets
    targets = [
        {"name": "DVWA", "url": "http://dvwa.local", "description": "Damn Vulnerable Web App"},
        {"name": "Juice Shop", "url": "http://juice-shop.local", "description": "OWASP Juice Shop"},
        {"name": "bWAPP", "url": "http://bwapp.local", "description": "buggy web application"},
    ]

    for target_data in targets:
        target = db.query(Target).filter(Target.name == target_data["name"]).first()
        if not target:
            target = Target(**target_data)
            db.add(target)
            logger.info(f"Target '{target.name}' created.")

    db.commit()

def main() -> None:
    logger.info("Creating initial data")
    db = SessionLocal()
    init_db(db)
    logger.info("Initial data created")

if __name__ == "__main__":
    main()
