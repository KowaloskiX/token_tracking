# backend/minerva/models/user.py
from venv import logger
from minerva.config.constants import PLAN_TYPES, PlanTypeLiteral, UserRole
from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, ClassVar
from datetime import datetime
from passlib.context import CryptContext
from bson import ObjectId
from .subscription import UserSubscription
from minerva.core.database.database import db
from enum import Enum

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class MarketingConsent(str, Enum):
    COMMUNICATION = "communication_emails"
    MARKETING = "marketing_emails"
    SOCIAL = "social_emails"
    SECURITY = "security_emails"

class User(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    org_id: Optional[str] = None
    email: EmailStr
    name: str
    google_id: Optional[str] = None
    avatar_img: Optional[str] = None
    role: UserRole = UserRole.MEMBER
    invited_by: Optional[PyObjectId] = None
    hashed_password: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    subscription: UserSubscription = Field(default_factory=lambda: UserSubscription(plan_type="free"))
    total_tokens: Optional[int] = 0
    daily_tokens: Optional[int] = 0
    last_token_reset: Optional[datetime] = Field(default_factory=datetime.utcnow)
    active: bool = True
    marketing_consent: dict[str, bool] = Field(
        default_factory=lambda: {
            "communication_emails": True,
            "marketing_emails": True,
            "social_emails": True,
            "security_emails": True
        }
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

    @classmethod
    async def get_by_stripe_customer_id(cls, customer_id: str) -> Optional['User']:
        user_doc = await db["users"].find_one({
            "subscription.stripe_customer_id": customer_id
        })
        if user_doc:
            return cls(**user_doc)
        return None

    @classmethod
    async def get_by_id(cls, user_id: str) -> Optional['User']:
        try:
            user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return cls(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error retrieving user by ID: {str(e)}")
            return None

    async def update(self, update_data: dict) -> bool:
        try:
            result = await db["users"].update_one(
                {"_id": self.id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return False

    @classmethod
    def hash_password(cls, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str) -> bool:
        if not self.hashed_password:
            return False
        return pwd_context.verify(plain_password, self.hashed_password)

    @property
    def effective_plan(self) -> PlanTypeLiteral:
        if self.org_id:
            return "enterprise"
        return self.subscription.plan_type

    def can_use_tokens(self, token_count: int) -> bool:
        """Check if user can use the specified number of tokens"""
        max_tokens = PLAN_TYPES[self.effective_plan]["max_daily_tokens"]
        if max_tokens is None:  # Enterprise users have unlimited tokens
            return True
        return (self.daily_tokens + token_count) <= max_tokens
