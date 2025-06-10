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
            "settings": {
                "analysis": {
                    "analyzer": {
                        "polish_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "polish_stop",
                                "polish_stemmer",
                                "asciifolding"
                            ]
                        }
                    },
                    "filter": {
                        "polish_stop": {
                            "type": "stop",
                            "stopwords": ["i", "a", "o", "z", "w", "na", "do", "od", "za", "po", "przy", "dla", "oraz", "albo", "lub", "ale", "lecz", "oraz", "także", "również"]
                        },
                        "polish_stemmer": {
                            "type": "stemmer",
                            "language": "light_polish"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "text": {
                        "type": "text",
                        "fields": {
                            "stemmed": {
                                "type": "text",
                                "analyzer": "polish_analyzer"
                            }
                        }
                    },
                    "date": {
                        "type": "text"
                    },
                    "metadata": {
                        "type": "object",
                        "dynamic": True,
                        "properties": {
                            "source": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            },
                            "sanitized_filename": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            },
                            "file_id": {
                                "type": "keyword"
                            },
                            "tender_pinecone_id": {
                                "type": "text",
                                "fields": {
                                    "keyword": {
                                        "type": "keyword"
                                    }
                                }
                            }
                        }
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
                    "type": "text",
                    "fields": {
                        "stemmed": {
                            "type": "text",
                            "analyzer": "polish_analyzer"
                        }
                    }
                },
                "initiation_date": {
                    "type": "text"
                },
                "metadata": {
                    "type": "object",
                    "dynamic": True,
                    "properties": {
                        "source": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "sanitized_filename": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "file_id": {
                            "type": "keyword"
                        },
                        "tender_pinecone_id": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        }
                    }
                }
            }
        }
        
        response = await es_client.indices.put_mapping(
            index=index_name,
            body=mappings
        )
        return {"created": False, "updated": True, "response": response}