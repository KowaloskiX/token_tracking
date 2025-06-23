# minerva/main.py (updated sections)
import os
from pathlib import Path
from minerva.api.routes import ai_routes, assistant_routes, conversation_routes, file_routes, folder_routes, notification_routes, organization_routes, scraping_routes, user_routes, waitlist_routes, retrieval_routes, kanban_board_routes, invitation_routes, comment_routes, reset_password_routes, api_key_routes, cost_tracking_routes, analytics_routes
from minerva.api.routes.api import results_routes
from minerva.api.routes.extensions.tenders import tender_analysis_routes, tender_description_filter_routes, tender_extract_routes, tender_monitoring_routes, tender_search_routes, tender_initial_ai_filtering_routes, tender_file_extraction_routes, tender_description_generation_routes, tender_criteria_analysis_routes, analysis_queue_routes
from minerva.api.routes.api import results_routes
from minerva.api.routes.stripe import stripe_routes, stripe_webhooks
from minerva.config import logging_config
from minerva.core.services.browser_service import browser_service_instance
from minerva.core.database.database import client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import logging
import nltk
nltk.download('punkt_tab')

# Load environment variables
load_dotenv()

import certifi
print("certifi:", certifi.where())

import ssl
print("SSL default verify paths:", ssl.get_default_verify_paths())

# Setup logging first, before anything else
logging_config.setup_logging()
logger = logging.getLogger("minerva.api")

logger.info("Initializing FastAPI application")

app = FastAPI(redirect_slashes=False)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://www.asystent.ai",
    "https://asystent-ai-ebon.vercel.app",
    "https://asystent-ai-git-main-piotr-gerkes-projects.vercel.app",
    "https://api.asystent.ai"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routes
app.include_router(kanban_board_routes.router, tags=["kanban-boards"])
app.include_router(organization_routes.router, prefix="/organizations", tags=["organizations"])
app.include_router(user_routes.router, prefix="/users", tags=["users"])
app.include_router(assistant_routes.router, prefix="/assistants", tags=["assistants"])
app.include_router(conversation_routes.router, prefix="/conversations", tags=["conversations"])
app.include_router(file_routes.router, prefix="/files", tags=["files"])
app.include_router(folder_routes.router, prefix="/folders", tags=["folders"])
app.include_router(waitlist_routes.router, prefix="/waitlist", tags=["waitlist"])
app.include_router(tender_extract_routes.router, prefix="/tender-extract", tags=["tendersextract"])
app.include_router(stripe_webhooks.router, prefix="/stripe/webhooks", tags=["stripe"]) 
app.include_router(stripe_routes.router, prefix="/stripe", tags=["stripe"])
app.include_router(retrieval_routes.router)
app.include_router(notification_routes.router)
app.include_router(tender_analysis_routes.router)
app.include_router(tender_monitoring_routes.router)
app.include_router(tender_search_routes.router)
app.include_router(tender_initial_ai_filtering_routes.router)
app.include_router(tender_description_filter_routes.router)
app.include_router(tender_file_extraction_routes.router)
app.include_router(tender_description_generation_routes.router)
app.include_router(tender_criteria_analysis_routes.router)
app.include_router(analysis_queue_routes.router, prefix="/analysis-queue", tags=["analysis-queue"])
app.include_router(ai_routes.router)
app.include_router(scraping_routes.router)
app.include_router(invitation_routes.router)
app.include_router(comment_routes.router, prefix="/comments", tags=["comments"])
app.include_router(reset_password_routes.router, tags=["reset-password"])
app.include_router(api_key_routes.router, prefix="/api-keys", tags=["api-keys"])
app.include_router(results_routes.router, prefix="/api", tags=["api"])
app.include_router(cost_tracking_routes.router, prefix="/cost-tracking", tags=["cost-tracking"])
app.include_router(analytics_routes.router, tags=["analytics"])

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.on_event("startup")
async def startup_event():
    try:
        # scheduler.start()
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB!")
        # Start the browser service
        await browser_service_instance.initialize()
        logger.info("Browser service initialized successfully!")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    client.close()
    logger.info("Application shutdown complete")

def start():
    logger.info("Starting FastAPI server on 0.0.0.0:8000")
    # Use import string for reload support
    uvicorn.run("minerva.api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()