from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import resend
from typing import Optional
import os
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

router = APIRouter()

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    html: str
    from_email: Optional[str] = "piotr@asystent.ai"

@router.post("/send-email")
async def send_email(email_request: EmailRequest):
    try:
        # Validate API key
        if not resend.api_key:
            raise HTTPException(
                status_code=500,
                detail="Resend API key not configured"
            )

        # Send email using Resend
        response = resend.Emails.send({
            "from": email_request.from_email,
            "to": email_request.to,
            "subject": email_request.subject,
            "html": email_request.html
        })

        return JSONResponse(
            content={"message": "Email sent successfully", "id": response["id"]},
            status_code=200
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )
