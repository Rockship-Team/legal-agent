"""Embedding service for Vietnamese legal text using PhoBERT-based model"""

import logging
import re
from typing import List, Optional

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import normalize_for_embedding

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates and manages embeddings for Vietnamese legal text.

    Model: bkai-foundation-models/vietnamese-bi-encoder (768d)
    Normalization: NFC (NOT NFD)
    Index: Supabase pgvector with HNSW
    """

    def __init__(self, model_name: str = None):
        settings = get_settings()
        self._model_name = model_name or settings.embedding_model
        self._dimension = settings.embedding_dimension
        self._model = None

    def get_model(self):
        """Lazy-load model (~1.1 GB RAM). Singleton per process."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            logger.info(
                f"Model loaded. Dimension: {self._model.get_sentence_embedding_dimension()}"
            )
        return self._model

    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        1. NFC normalize (NOT NFD)
        2. Collapse whitespace
        3. Encode with normalize_embeddings=True
        4. Return as list[float] (768 dimensions)
        """
        text = normalize_for_embedding(text)
        model = self.get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently.

        1. NFC normalize all texts
        2. Sort by length (minimize padding waste)
        3. Batch encode
        4. Restore original order
        5. Return as list of list[float]
        """
        if not texts:
            return []

        # Normalize all texts
        normalized = [normalize_for_embedding(t) for t in texts]

        # Sort by length with original indices for order restoration
        indexed = list(enumerate(normalized))
        indexed.sort(key=lambda x: len(x[1]))

        sorted_texts = [t for _, t in indexed]
        original_indices = [i for i, _ in indexed]

        # Batch encode
        model = self.get_model()
        embeddings = model.encode(
            sorted_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(sorted_texts) > 100,
        )

        # Restore original order
        result = [None] * len(texts)
        for sorted_idx, orig_idx in enumerate(original_indices):
            result[orig_idx] = embeddings[sorted_idx].tolist()

        return result

    def embed_and_store(
        self,
        db,
        articles: List[dict],
        batch_size: int = 64,
        upsert_chunk_size: int = 50,
    ) -> int:
        """Full pipeline: embed texts + upsert to database.

        1. Split long articles if needed
        2. Extract content from articles
        3. embed_batch() all contents
        4. Upsert to articles table in chunks
        5. Returns total articles stored
        """
        if not articles:
            return 0

        # Split long articles
        all_articles = []
        for article in articles:
            chunks = self.split_long_article(article)
            all_articles.extend(chunks)

        # Extract content for embedding
        texts = [a["content"] for a in all_articles]

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} articles...")
        embeddings = self.embed_batch(texts, batch_size=batch_size)

        # Attach embeddings to articles
        for article, embedding in zip(all_articles, embeddings):
            article["embedding"] = embedding

        # Upsert in chunks
        total = db.upsert_articles(all_articles)
        logger.info(f"Stored {total} articles with embeddings")
        return total

    def split_long_article(
        self, article: dict, max_chars: int = 380
    ) -> List[dict]:
        """Split articles exceeding model token limit.

        max_chars=380 ≈ 256 PhoBERT tokens.
        Splits by Khoản (clause), prepends Điều header to each chunk.
        Sets chunk_index > 0 for splits.
        """
        content = article.get("content", "")
        if len(content) <= max_chars:
            return [article]

        # Extract Điều header
        header_match = re.match(
            r"(Điều\s+\d+\.?\s*[^\n]*)", content, re.IGNORECASE
        )
        header = header_match.group(1) if header_match else ""

        # Split by Khoản (clause): numbered items like "1. ...", "2. ..."
        clauses = re.split(r"(?=\n\s*\d+\.\s+)", content)

        chunks = []
        current_chunk = ""
        chunk_index = 0

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            # If adding this clause exceeds limit, save current chunk
            if current_chunk and len(current_chunk + "\n" + clause) > max_chars:
                chunks.append(self._make_chunk(article, current_chunk, chunk_index, header))
                chunk_index += 1
                current_chunk = header + "\n" + clause if header and chunk_index > 0 else clause
            else:
                current_chunk = (
                    current_chunk + "\n" + clause if current_chunk else clause
                )

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(self._make_chunk(article, current_chunk, chunk_index, header))

        return chunks if chunks else [article]

    def _make_chunk(
        self, article: dict, content: str, chunk_index: int, header: str
    ) -> dict:
        """Create a chunk dict from article and content."""
        chunk = dict(article)
        chunk["content"] = content
        chunk["chunk_index"] = chunk_index
        # Generate a deterministic UUID for chunks
        if chunk_index > 0:
            import uuid as _uuid
            base_id = article.get("id", "")
            chunk["id"] = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{base_id}_chunk_{chunk_index}")) if base_id else ""
        return chunk
