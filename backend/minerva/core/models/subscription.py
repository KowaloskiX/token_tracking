from minerva.config.constants import PLAN_TYPES, BillingIntervalLiteral, PlanTypeLiteral
from pydantic import BaseModel
from typing import Optional


class SubscriptionBase(BaseModel):
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: Optional[str] = None
    billing_interval: Optional[BillingIntervalLiteral] = None

    @property
    def max_daily_tokens(self) -> Optional[int]:
        return PLAN_TYPES[self.plan_type]["max_daily_tokens"]

class UserSubscription(SubscriptionBase):
    plan_type: PlanTypeLiteral = "free"

class OrganizationSubscription(SubscriptionBase):
    plan_type: PlanTypeLiteral = "enterprise"