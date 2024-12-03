from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import hash_password

# Add test users
def seed_users(db: Session):
    test_users = [
        {"name": "Alice", "email": "alice@example.com", "password": "password1"},
        {"name": "Bob", "email": "bob@example.com", "password": "password2"},
        {"name": "Charlie", "email": "charlie@example.com", "password": "password3"},
        {"name": "Diana", "email": "diana@example.com", "password": "password4"},
    ]
    for user in test_users:
        hashed_password = hash_password(user["password"])
        new_user = User(name=user["name"], email=user["email"], password_hash=hashed_password)
        db.add(new_user)
    db.commit()
    print("Seeded test users successfully.")

from models import Climb

def seed_climbs(db: Session):
    climbs = [
        {"name": "El Capitan", "location": "Yosemite National Park"},
        {"name": "Half Dome", "location": "Yosemite National Park"},
        {"name": "Mount Rainier", "location": "Washington"},
        {"name": "Devils Tower", "location": "Wyoming"},
    ]
    for climb in climbs:
        new_climb = Climb(name=climb["name"], location=climb["location"])
        db.add(new_climb)
    db.commit()
    print("Seeded test climbs successfully.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        #seed_users(db)
        seed_climbs(db)
    finally:
        db.close()
