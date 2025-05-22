import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from minerva.core.middleware.auth.jwt import get_current_user
from minerva.core.services.stripe.stripe_service import StripeService
from pydantic import BaseModel
import stripe

load_dotenv()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

router = APIRouter()

class PriceIds(BaseModel):
    monthly: str
    annual: str
    monthly_price: float
    annual_price: float
    currency: str

class CheckoutSessionRequest(BaseModel):
    price_id: str
    interval: str
    success_url: str
    cancel_url: str

class PortalSessionRequest(BaseModel):
    customer_id: str
    return_url: str

@router.get("/prices", response_model=PriceIds)
async def get_price_ids():
    monthly_price_id = os.getenv('STRIPE_MONTHLY_PRICE_ID')
    annual_price_id = os.getenv('STRIPE_ANNUAL_PRICE_ID')

    # Fetch price details from Stripe
    monthly_price = stripe.Price.retrieve(monthly_price_id)
    annual_price = stripe.Price.retrieve(annual_price_id)

    return PriceIds(
        monthly=monthly_price_id,
        annual=annual_price_id,
        monthly_price=monthly_price.unit_amount / 100,  # Convert from cents to whole currency
        annual_price=annual_price.unit_amount / 100,
        currency=monthly_price.currency
    )

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user = Depends(get_current_user)
):
    
    session = await StripeService.create_checkout_session(
        user_id=str(current_user.id),
        price_id=request.price_id,
        interval=request.interval,
        success_url=request.success_url,
        cancel_url=request.cancel_url
    )
    return session  # Return the entire session object including the URL

@router.post("/create-portal-session")
async def create_portal_session(
    request: PortalSessionRequest,
    current_user = Depends(get_current_user)
):
    try:
        # Create Stripe billing portal session
        session = stripe.billing_portal.Session.create(
            customer=request.customer_id,
            return_url=request.return_url,
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


