from typing import Any, Dict, Literal
from enum import Enum as PyEnum

# Define literal types for plan types and billing intervals
PlanTypeLiteral = Literal["free", "standard", "enterprise"]
BillingIntervalLiteral = Literal["monthly", "yearly"]

PLAN_TYPES: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",  # Name of the plan
        "max_daily_tokens": 50000,  # Maximum tokens allowed per day
    },
    "standard": {
        "name": "Standard",  # Name of the plan
        "max_daily_tokens": 1000000,  # Maximum tokens allowed per day
    },
    "enterprise": {
        "name": "Enterprise",  # Name of the plan
        "max_daily_tokens": 1000000000000,  # Maximum tokens allowed per day
    }
}

# List of all available data sources
ALL_SOURCES = ["ezamowienia"]

# Enum class representing user roles
class UserRole(str, PyEnum):
    ADMIN = "admin"    # Can manage users, send invitations, etc.
    MEMBER = "member"  # Standard user with basic access
    GUEST = "guest"    # Limited access (e.g., view-only)

# List of all user roles as strings
USER_ROLES = [role.value for role in UserRole]
