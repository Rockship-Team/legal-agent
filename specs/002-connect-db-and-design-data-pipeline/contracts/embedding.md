# Embedding Service Module Contract

## Overview
The Embedding service generates vector embeddings for Vietnamese legal text using a PhoBERT-based model, with NFC normalization and Supabase pgvector storage.

## Interface

### EmbeddingService

```python
# services/embedding.py
from typing import List, Optional
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    """Generates and manages embeddings for Vietnamese legal text.

    Model: bkai-foundation-models/vietnamese-bi-encoder (768d)
    Normalization: NFC (NOT NFD)
    Index: Supabase pgvector with HNSW
    """

    def __init__(self, model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"):
        self._model: Optional[SentenceTransformer] = None
        self._model_name = model_name

    def get_model(self) -> SentenceTransformer:
        """Lazy-load model (~1.1 GB RAM). Singleton per process."""
        pass

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        1. NFC normalize (NOT NFD)
        2. Collapse whitespace
        3. Encode with normalize_embeddings=True
        4. Return as list[float] (768 dimensions)
        """
        pass

    def embed_batch(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.

        1. NFC normalize all texts
        2. Sort by length (minimize padding waste)
        3. Batch encode
        4. Restore original order
        5. Return as list of list[float]
        """
        pass

    def embed_and_store(self, db, articles: list[dict],
                        batch_size: int = 64,
                        upsert_chunk_size: int = 50) -> int:
        """Full pipeline: embed texts + upsert to Supabase.

        1. Extract content from articles
        2. embed_batch() all contents
        3. Upsert to articles table in chunks of 50
        4. Returns total articles stored
        """
        pass

    def split_long_article(self, article: dict, max_chars: int = 380) -> list[dict]:
        """Split articles exceeding model token limit.

        max_chars=380 ≈ 256 PhoBERT tokens.
        Splits by Khoản (clause), prepends Điều header to each chunk.
        Sets chunk_index > 0 for splits.
        """
        pass
```

### Text Normalization

```python
# utils/vietnamese.py — EXTENSION

def normalize_for_embedding(text: str) -> str:
    """NFC normalize for PhoBERT-based embedding models.

    CRITICAL: PhoBERT was trained on NFC text.
    Using NFD decomposes diacritics into combining marks,
    producing completely different token sequences.

    Rules:
    - NFC normalize (NOT NFD)
    - Collapse whitespace
    - Do NOT lowercase
    - Do NOT remove diacritics
    - Do NOT remove stop words
    """
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    return text.strip()
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `vietnamese-bi-encoder` over MiniLM | 93.59% Acc@10 on legal retrieval vs generic multilingual |
| 768d over 384d | Model output dimension, more expressive for legal vocabulary |
| NFC over NFD | PhoBERT tokenizer trained on NFC; NFD breaks tokenization |
| HNSW over IVFFlat | Self-updating index, no rebuild needed after inserts |
| Sort by length before batch | Minimizes padding waste, 20-30% throughput improvement |
| `normalize_embeddings=True` | L2-normalized vectors make cosine distance computation faster |
| Split by Khoản | Preserves legal structure; Điều header provides context |

## Memory Budget

| Component | RAM |
|-----------|-----|
| Model load | ~1.1 GB |
| 500 embeddings (768d, float32) | ~1.5 MB |
| Tokenizer buffers (batch=64) | ~300-500 MB peak |
| **Total peak** | **~1.6 GB on CPU** |

## Testing Contract

```python
def test_embed_single_returns_768d():
    """Embedding should be 768 dimensions"""
    emb = service.embed_single("Điều kiện chuyển nhượng quyền sử dụng đất")
    assert len(emb) == 768
    assert all(isinstance(v, float) for v in emb)

def test_embed_batch_preserves_order():
    """Batch embedding should maintain input order"""
    texts = ["short", "a much longer text about legal matters"]
    embs = service.embed_batch(texts)
    assert len(embs) == 2
    # Verify order preserved despite length-sorting

def test_nfc_normalization():
    """Should use NFC, not NFD"""
    text = "hợp đồng"  # precomposed
    normalized = normalize_for_embedding(text)
    assert unicodedata.is_normalized("NFC", normalized)

def test_split_long_article():
    """Should split articles exceeding token limit"""
    article = {"content": "Điều 1. Title\n1. First clause...\n2. Second clause...",
               "article_number": 1, "id": "test"}
    chunks = service.split_long_article(article, max_chars=50)
    assert len(chunks) >= 2
    assert chunks[0]["chunk_index"] == 0

def test_embed_and_store():
    """Should embed and upsert to database"""
    count = service.embed_and_store(db, articles)
    assert count == len(articles)
```
