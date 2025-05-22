import os
from dotenv import load_dotenv
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# Load environment variables
MONGODB_URI = os.getenv("MONGODB_URI")

# Establish a synchronous MongoDB client connection
client = AsyncIOMotorClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.Main