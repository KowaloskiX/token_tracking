from datetime import datetime
from decimal import Decimal
import json
import logging
import os
from minerva.core.database.database import db
from openai import OpenAI

openai = OpenAI()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

class FunctionHandler:
    def __init__(self):
        self.google_maps_api_key = os.getenv('GOOGLE_MAPS_API_KEY')

    def example_function(self, tool):
        arguments = json.loads(tool['function']['arguments'])
        return {
            "tool_call_id": tool['id'],
            "output": arguments
        }

        
    def handle_function_call(self, tool_calls):
        for tool in tool_calls:
            function_name = tool['function']['name']
            handler_method = getattr(self, f'handle_{function_name}', None)
            
            if handler_method:
                tool_output = handler_method(tool)
                return tool_output, tool["thread_id"], tool["run_id"]
        
        return None, None, None