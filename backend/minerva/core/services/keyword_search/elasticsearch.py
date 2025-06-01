import os
from elasticsearch import AsyncElasticsearch
from dotenv import load_dotenv
load_dotenv()

# es_client = Elasticsearch(
#     os.getenv("ELASTICSEARCH_URL"),
#     api_key=os.getenv("ELASTICSEARCH_API_KEY")
# )

ES_REQUEST_TIMEOUT = int(os.getenv("ELASTICSEARCH_REQUEST_TIMEOUT", "450"))

# Configure AsyncElasticsearch with a higher default timeout to reduce bulk-upload failures.
es_client = AsyncElasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTICSEARCH_API_KEY"),
    http_compress=True,
    request_timeout=ES_REQUEST_TIMEOUT,
    max_retries=3,
    retry_on_timeout=True,
)

index_name = "asystent-ai"

async def create_index_with_mappings(es_client, index_name):
    if not await es_client.indices.exists(index=index_name):
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
        
        response = await es_client.indices.create(
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
        
        response = await es_client.indices.put_mapping(
            index=index_name,
            body=mappings
        )
        return {"created": False, "updated": True, "response": response}