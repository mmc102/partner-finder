from sqlalchemy import Column, Integer, String, ForeignKey, Table, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class UserAssociation(Base):
    __tablename__ = "user_associations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    friend_id = Column(Integer, ForeignKey("users.id"))
    followed_at = Column(DateTime, default=datetime.utcnow)  # New field for when the user followed
    user = relationship("User", foreign_keys=[user_id], back_populates="following")
    friend = relationship("User", foreign_keys=[friend_id], back_populates="followers")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    source_user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String, index=True)
    read = Column(Boolean, default=False)
    timestamp = Column(String, default=datetime.utcnow)
    notification_type = Column(String, default="general")

    # Relationship for the user who receives the notification
    user = relationship("User", back_populates="notifications", foreign_keys=[user_id])

    # Relationship for the user who triggered the notification (the source user)
    source_user = relationship("User", back_populates="sent_notifications", foreign_keys=[source_user_id])


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

    # 'user_id' in the user_associations table represents the user who is following
    following = relationship("UserAssociation", foreign_keys=[UserAssociation.user_id], back_populates="user")

    # 'friend_id' in the user_associations table represents the user being followed
    followers = relationship("UserAssociation", foreign_keys=[UserAssociation.friend_id], back_populates="friend")

    interests = relationship("UserInterest", back_populates="user")
    feed_items = relationship("FeedItem", back_populates="user")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic", foreign_keys=[Notification.user_id])
    sent_notifications = relationship("Notification", back_populates="source_user", foreign_keys=[Notification.source_user_id])

class Climb(Base):
    __tablename__ = "climbs"
    id = Column(String, primary_key=True, index=True)  # Ensure id is String
    name = Column(String, nullable=False)
    grade_yds = Column(String, nullable=True)  # YDS grading
    grade_font = Column(String, nullable=True)  # Font grading
    description = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    protection = Column(String, nullable=True)
    area_id = Column(String, ForeignKey("areas.id"), nullable=False)  # Foreign key to Area
    latitude = Column(Float, nullable=True)  # Latitude field
    longitude = Column(Float, nullable=True)  # Longitude field

    area = relationship("Area", back_populates="climbs")

# User Interests Table
class UserInterest(Base):
    __tablename__ = "user_interests"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    climb_id = Column(String, ForeignKey("climbs.id"), nullable=False)

    user = relationship("User")
    climb = relationship("Climb")

class FeedItem(Base):
    __tablename__ = "feed_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g., "added_friend", "completed_climb"
    details = Column(Text, nullable=True)    # Optional details (e.g., climb name or friend name)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="feed_items")

class Area(Base):
    __tablename__ = "areas"
    id = Column(String, primary_key=True, index=True)  # Change id to String type
    name = Column(String, nullable=False)
    parent_id = Column(String, ForeignKey("areas.id"), nullable=True)  # Change parent_id to String
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    children = relationship("Area", backref="parent", remote_side=[id])
    climbs = relationship("Climb", back_populates="area")
