import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
load_dotenv()

es_client = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTICSEARCH_API_KEY")
)

index_name = "asystent-ai"

def create_index_with_mappings(es_client, index_name):
    if not es_client.indices.exists(index=index_name):
        # Create index with mappings
        mappings = {
            "mappings": {
                "properties": {
                    "text": {
                        "type": "text"
                    },
                    "date": {
                        "type": "text"
                    },
                    "metadata": {
                        "type": "object",
                        "dynamic": True
                    }
                }
            }
        }
        
        response = es_client.indices.create(
            index=index_name,
            body=mappings
        )
        return {"created": True, "response": response}
    else:
        # Update existing index mapping
        mappings = {
            "properties": {
                "text": {
                    "type": "text"
                },
                "initiation_date": {
                    "type": "text"
                },
                "metadata": {
                    "type": "object",
                    "dynamic": True
                }
            }
        }
        
        response = es_client.indices.put_mapping(
            index=index_name,
            body=mappings
        )
        return {"created": False, "updated": True, "response": response}