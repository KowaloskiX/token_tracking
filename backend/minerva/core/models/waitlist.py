from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class WaitlistEntry(BaseModel):
    email: EmailStr
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }