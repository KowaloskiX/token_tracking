import tiktoken
from pydantic import BaseModel

class ChunkingConfig(BaseModel):
    chunk_size: int = 750
    chunk_overlap: int = 150
    tokenizer_name: str = "cl100k_base"


def count_tokens(text, model="text-embedding-3-large"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

MAX_TOKENS = 8192 - 100

def safe_chunk_text(text, chunker, embedding_model):
    for chunk in chunker.create_chunks(text):
        if count_tokens(chunk, embedding_model) <= MAX_TOKENS:
            yield chunk
        else:
            # Split further if needed (rare, but possible with huge sentences)
            words = chunk.split()
            subchunk = []
            sublen = 0
            for word in words:
                wlen = count_tokens(word, embedding_model)
                if sublen + wlen > MAX_TOKENS:
                    yield " ".join(subchunk)
                    subchunk = [word]
                    sublen = wlen
                else:
                    subchunk.append(word)
                    sublen += wlen
            if subchunk:
                yield " ".join(subchunk)