# backend/minerva/api/routes/stripe_webhooks.py
import os
from fastapi import APIRouter, Request, HTTPException
from minerva.core.services.stripe.stripe_service import StripeService
import stripe
import logging
import json
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        if event.type == "customer.subscription.created":
            subscription = event.data['object']
            await StripeService.handle_subscription_created(subscription)
            
        elif event.type == "customer.subscription.updated":
            subscription = event.data['object']
            await StripeService.handle_subscription_updated(subscription)
            
        elif event.type == "customer.subscription.deleted":
            subscription = event.data['object']
            await StripeService.handle_subscription_deleted(subscription)
            
        return {"status": "success"}
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        # Log the full event data for debugging
        try:
            event_data = json.loads(payload)
            logger.error(f"Event data: {json.dumps(event_data, indent=2)}")
        except:
            pass
        return {"status": "error", "message": str(e)}