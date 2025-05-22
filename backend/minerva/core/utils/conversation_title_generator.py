from minerva.core.models.request.ai import LLMConfig
from minerva.core.services.llm_providers import openai
from minerva.core.database.database import db
from bson import ObjectId


async def generate_and_update_conversation_title(conversation_id, prompt):
    llm = openai.OpenAILLM(
        model="gpt-4.1-nano",
        stream=False,
        temperature=0.6,
        max_tokens=50,
        instructions="You generate brief 2-3 word titles that are on point for the conversations."
    )
    
    title_response = await llm.generate_response([
        {"role": "user", "content": f"Conversation content: '{prompt}' \nRespond just with the concise 2-3 word title for it:"}
    ])
    
    title = title_response.strip().replace('"', '').replace("'", '')
    
    db['conversations'].update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {
                "title": title
            }
        }
    )