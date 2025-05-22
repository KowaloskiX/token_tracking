from minerva.config.constants import BillingIntervalLiteral
from minerva.core.models.utils import PyObjectId
from pydantic import BaseModel, Field
from typing import Literal, Optional
from bson import ObjectId


class OrganizationSubscription(BaseModel):
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: Optional[str] = None  # active, canceled
    billing_interval: Optional[BillingIntervalLiteral] = None

class Organization(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    subscription: Optional[OrganizationSubscription] = Field(default_factory=OrganizationSubscription)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        populate_by_name = True
