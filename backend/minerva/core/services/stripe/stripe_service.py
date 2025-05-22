# backend/minerva/services/stripe_service.py
import datetime
import stripe
import os
from dotenv import load_dotenv
from minerva.core.models.user import User
from minerva.core.models.subscription import UserSubscription
from fastapi import HTTPException

load_dotenv()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class StripeService:
    @staticmethod
    async def create_checkout_session(
        user_id: str, 
        price_id: str, 
        interval: str,
        success_url: str,
        cancel_url: str
    ):
        try:
            user = await User.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Get or create customer
            customer_id = None
            if user.subscription and user.subscription.stripe_customer_id:
                customer_id = user.subscription.stripe_customer_id
                
            if not customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    metadata={"user_id": str(user.id)}
                )
                customer_id = customer.id
                
                # Create initial subscription state
                initial_subscription = UserSubscription(
                    stripe_customer_id=customer_id,
                    plan_type="free",
                    status="incomplete"
                )
                
                # Update user with the new subscription
                await user.update({
                    "subscription": initial_subscription.dict()
                })
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user.id),
                    "interval": interval
                }
            )
            return {"url": session.url}
        except Exception as e:
            print(f"Error in create_checkout_session: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @staticmethod
    async def handle_subscription_updated(subscription):
        customer_id = subscription['customer']
        user = await User.get_by_stripe_customer_id(customer_id)
        
        if not user:
            return
        
        # Update user subscription
        plan_type = "standard" if subscription['status'] == "active" else "free"
        billing_interval = "monthly" if subscription['items']['data'][0]['price']['recurring']['interval'] == "month" else "yearly"
        
        updated_subscription = UserSubscription(
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription['id'],
            status=subscription['status'],
            plan_type=plan_type,
            billing_interval=billing_interval
        )
        
        await user.update({"subscription": updated_subscription.dict()})

    @staticmethod
    async def handle_subscription_deleted(subscription: stripe.Subscription):
        customer_id = subscription.customer
        user = await User.get_by_stripe_customer_id(customer_id)
        
        if not user:
            return
        
        # Reset to free plan
        free_subscription = UserSubscription(
            plan_type="free",
            stripe_customer_id=customer_id,
            stripe_subscription_id=None,
            status="canceled"
        )
        
        await user.update({"subscription": free_subscription.dict()})



    @staticmethod
    async def handle_subscription_created(subscription):
        customer_id = subscription['customer']
        user = await User.get_by_stripe_customer_id(customer_id)
        
        if not user:
            return
        
        # Set initial subscription state
        plan_type = "standard" if subscription['status'] == "active" else "free"
        billing_interval = "monthly" if subscription['items']['data'][0]['price']['recurring']['interval'] == "month" else "yearly"
        
        updated_subscription = UserSubscription(
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription['id'],
            status=subscription['status'],
            plan_type=plan_type,
            billing_interval=billing_interval
        )
        
        # Update user with new subscription
        await user.update({
            "subscription": updated_subscription.dict(),
            "daily_tokens": 0,  # Reset tokens when subscription starts
            "last_token_reset": datetime.utcnow()
        })