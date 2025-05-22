import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import nltk
nltk.download('punkt')

import tiktoken
from nltk.tokenize import sent_tokenize
from typing import List, Optional
from pydantic import BaseModel

class ChunkingConfig(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 100
    tokenizer_name: str = "cl100k_base"

class TextChunker:
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.tokenizer = tiktoken.get_encoding(self.config.tokenizer_name)

    def create_chunks(self, text: str, chunk_size: Optional[int] = None) -> List[str]:
        if not text or text.isspace():
            return []

        sentences = sent_tokenize(text)
        
        # Determine the effective chunk size and overlap from config or parameters
        effective_chunk_size = chunk_size if chunk_size is not None else self.config.chunk_size
        effective_overlap_tokens = self.config.chunk_overlap

        chunks = []
        current_chunk_sentences = []
        current_chunk_tokens = 0

        for sentence_text in sentences:
            sentence_token_ids = self.tokenizer.encode(sentence_text)
            sentence_token_count = len(sentence_token_ids)

            # Case 1: The current sentence itself is larger than the effective_chunk_size
            if sentence_token_count > effective_chunk_size:
                # First, add any existing current_chunk_sentences to chunks
                if current_chunk_sentences:
                    chunks.append(" ".join(current_chunk_sentences).strip())
                    current_chunk_sentences = []
                    current_chunk_tokens = 0
                
                # Now, split the oversized sentence_token_ids
                sub_chunk_start_idx = 0
                while sub_chunk_start_idx < sentence_token_count:
                    sub_chunk_end_idx = min(sub_chunk_start_idx + effective_chunk_size, sentence_token_count)
                    sub_chunk_token_ids = sentence_token_ids[sub_chunk_start_idx:sub_chunk_end_idx]
                    chunks.append(self.tokenizer.decode(sub_chunk_token_ids).strip())
                    
                    # Determine start for the next sub-chunk with overlap
                    if sub_chunk_end_idx < sentence_token_count: # If not the last sub-chunk
                        overlap_start = max(0, sub_chunk_end_idx - effective_overlap_tokens)
                        # Ensure progression, if overlap is too large or chunk too small
                        sub_chunk_start_idx = overlap_start if overlap_start < sub_chunk_end_idx else sub_chunk_end_idx
                    else: # This was the last sub-chunk
                        sub_chunk_start_idx = sub_chunk_end_idx
                continue # Move to the next sentence in the outer loop

            # Case 2: Adding the current sentence would make the current chunk too large
            if current_chunk_tokens + sentence_token_count > effective_chunk_size:
                if current_chunk_sentences: # Finalize and add the current chunk
                    chunks.append(" ".join(current_chunk_sentences).strip())
                
                # Start a new chunk with overlap from the previous one
                # Build overlap based on sentences from the end of the previous chunk
                overlap_sentences_for_new_chunk = []
                overlap_tokens_count = 0
                for prev_sentence_idx in range(len(current_chunk_sentences) - 1, -1, -1):
                    prev_sentence_text = current_chunk_sentences[prev_sentence_idx]
                    prev_sentence_tokens = len(self.tokenizer.encode(prev_sentence_text))
                    if overlap_tokens_count + prev_sentence_tokens > effective_overlap_tokens:
                        break
                    overlap_sentences_for_new_chunk.insert(0, prev_sentence_text) # Add to the beginning
                    overlap_tokens_count += prev_sentence_tokens
                
                current_chunk_sentences = overlap_sentences_for_new_chunk
                current_chunk_tokens = overlap_tokens_count

                # If the current sentence *still* makes the new chunk (with overlap) too big,
                # then the overlap must be reduced or the sentence starts a completely new chunk.
                # For simplicity, if sentence + overlap > size, start new chunk with just sentence.
                # This assumes sentence_token_count <= effective_chunk_size (handled by Case 1).
                if current_chunk_tokens + sentence_token_count > effective_chunk_size:
                    current_chunk_sentences = [sentence_text] # current_chunk has only this sentence
                    current_chunk_tokens = sentence_token_count
                else:
                    current_chunk_sentences.append(sentence_text)
                    current_chunk_tokens += sentence_token_count
            
            # Case 3: Sentence fits into the current chunk
            else:
                current_chunk_sentences.append(sentence_text)
                current_chunk_tokens += sentence_token_count

        # Add any remaining sentences in current_chunk_sentences
        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences).strip())

        return [chunk for chunk in chunks if chunk] # Filter out any potential empty chunks