# backend/minerva/models/user.py
from venv import logger
from minerva.config.constants import PLAN_TYPES, PlanTypeLiteral, UserRole
from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, ClassVar, List
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

class LoginEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    login_method: str  # "email_password", "google_oauth"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class User(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    org_id: Optional[str] = None
    email: EmailStr
    name: str
    google_id: Optional[str] = None
    avatar_img: Optional[str] = None
    role: UserRole = UserRole.ADMIN
    invited_by: Optional[PyObjectId] = None
    hashed_password: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    subscription: UserSubscription = Field(default_factory=lambda: UserSubscription(plan_type="enterprise"))
    total_tokens: Optional[int] = 0
    daily_tokens: Optional[int] = 0
    last_token_reset: Optional[datetime] = Field(default_factory=datetime.utcnow)
    active: bool = True
    preferred_language: Optional[str] = Field(default="pl")  # User's preferred language (pl, en, de)
    marketing_consent: dict[str, bool] = Field(
        default_factory=lambda: {
            "communication_emails": True,
            "marketing_emails": True,
            "social_emails": True,
            "security_emails": True
        }
    )
    # Login tracking fields
    last_login: Optional[datetime] = None
    login_history: List[LoginEvent] = Field(default_factory=list)
    login_count: int = 0

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

    async def can_leave_organization(self) -> tuple[bool, str]:
        """
        Check if user can safely leave their organization.
        Returns (can_leave, reason_if_cannot)
        """
        if not self.org_id:
            return False, "User is not in any organization"
        
        # Count total members in the organization
        member_count = await db["users"].count_documents({"org_id": self.org_id})
        
        # If user is the only member, they can always leave
        if member_count <= 1:
            return True, ""
        
        # If user is not an admin, they can leave
        if self.role != UserRole.ADMIN:
            return True, ""
        
        # If user is admin, check if there are other admins
        admin_count = await db["users"].count_documents({
            "org_id": self.org_id,
            "role": "admin",
            "_id": {"$ne": self.id}  # Exclude current user
        })
        
        if admin_count == 0:
            return False, "Cannot leave as you are the only admin. Please assign another admin first."
        
        return True, ""

    async def get_organization_member_count(self) -> int:
        """Get the number of members in the user's organization"""
        if not self.org_id:
            return 0
        return await db["users"].count_documents({"org_id": self.org_id})

    async def record_login(self, login_method: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Record a login event for analytics tracking"""
        try:
            now = datetime.utcnow()
            login_event = LoginEvent(
                timestamp=now,
                login_method=login_method,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # Update user document with login information
            update_data = {
                "$set": {
                    "last_login": now
                },
                "$inc": {
                    "login_count": 1
                },
                "$push": {
                    "login_history": {
                        "$each": [login_event.dict()],
                        "$slice": -100  # Keep only the last 100 login events
                    }
                }
            }
            
            result = await db["users"].update_one(
                {"_id": self.id},
                update_data
            )
            
            if result.modified_count > 0:
                # Update local instance
                self.last_login = now
                self.login_count += 1
                self.login_history.append(login_event)
                # Keep only last 100 events in memory too
                if len(self.login_history) > 100:
                    self.login_history = self.login_history[-100:]
                
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error recording login for user {self.id}: {str(e)}")
            return False
