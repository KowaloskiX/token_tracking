from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from bson import ObjectId
from minerva.core.models.utils import PyObjectId  # Ensure this file exists and works similar to your Invitation model

# Model representing a password reset token
class PasswordResetToken(BaseModel):
    # Unique identifier for the token, using a custom ObjectId type
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    # Email address associated with the password reset request
    email: EmailStr
    # The actual reset token string
    token: str
    # Expiration date and time for the token
    expires_at: datetime
    # Indicates whether the password has been successfully reset
    changed: bool = False
    # Timestamp when the token was created
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Allow population of fields by their alias names
        allow_population_by_field_name = True
        # Allow arbitrary types like ObjectId
        arbitrary_types_allowed = True
        # Custom JSON encoders for ObjectId and datetime
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }