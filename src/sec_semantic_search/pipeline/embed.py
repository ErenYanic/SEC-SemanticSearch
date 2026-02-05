"""Embedding generation using sentence-transformers.

This module generates vector embeddings for text chunks using a
sentence-transformer model. It supports GPU acceleration and batch
processing for efficiency.

Usage:
    from sec_semantic_search.pipeline import EmbeddingGenerator

    generator = EmbeddingGenerator()
    embeddings = generator.embed_chunks(chunks)
    query_embedding = generator.embed_query("What are the risk factors?")
"""

import os
from typing import TYPE_CHECKING

import numpy as np
import torch

from sec_semantic_search.config import EMBEDDING_DIMENSION, get_settings
from sec_semantic_search.core import Chunk, EmbeddingError, get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generates vector embeddings using sentence-transformers.

    This class wraps the sentence-transformers library to provide
    GPU-accelerated embedding generation. The model is loaded lazily
    on first use to avoid unnecessary initialisation.

    Attributes:
        model_name: Name of the sentence-transformer model
        device: Device to run model on ('cuda', 'cpu', or 'auto')
        batch_size: Batch size for encoding

    Example:
        >>> generator = EmbeddingGenerator()
        >>> embeddings = generator.embed_chunks(chunks)
        >>> print(f"Generated {len(embeddings)} embeddings of dim {embeddings.shape[1]}")
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        """Initialise the embedding generator.

        Args:
            model_name: Model name. If None, uses settings.
            device: Device ('cuda', 'cpu', 'auto'). If None, uses settings.
            batch_size: Batch size for encoding. If None, uses settings.
        """
        settings = get_settings()

        self.model_name = model_name or settings.embedding.model_name
        self._device_setting = device or settings.embedding.device
        self.batch_size = batch_size or settings.embedding.batch_size

        # Set HF token if available (for faster downloads)
        hf_token = settings.hugging_face.token
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token

        # Model loaded lazily
        self._model: "SentenceTransformer | None" = None

        logger.debug(
            "EmbeddingGenerator configured: model=%s, device=%s, batch_size=%d",
            self.model_name,
            self._device_setting,
            self.batch_size,
        )

    @property
    def device(self) -> str:
        """Get the actual device being used.

        Returns:
            Device string ('cuda' or 'cpu').
        """
        if self._device_setting == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return self._device_setting

    @property
    def model(self) -> "SentenceTransformer":
        """Get or load the sentence-transformer model.

        The model is loaded lazily on first access to avoid
        unnecessary initialisation if embeddings aren't needed.

        Returns:
            Loaded SentenceTransformer model.

        Raises:
            EmbeddingError: If model loading fails.
        """
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> "SentenceTransformer":
        """Load the sentence-transformer model.

        Returns:
            Loaded model on configured device.

        Raises:
            EmbeddingError: If loading fails.
        """
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading embedding model '%s' on %s",
                self.model_name,
                self.device,
            )

            model = SentenceTransformer(self.model_name, device=self.device)

            # Log GPU info if using CUDA
            if self.device == "cuda":
                gpu_name = torch.cuda.get_device_name(0)
                logger.info("Using GPU: %s", gpu_name)

            return model

        except Exception as e:
            raise EmbeddingError(
                f"Failed to load model '{self.model_name}'",
                details=str(e),
            ) from e

    def embed_texts(
        self,
        texts: list[str],
        show_progress: bool = True,
    ) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.
            show_progress: Whether to show progress bar.

        Returns:
            NumPy array of shape (n_texts, embedding_dim).

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            raise EmbeddingError(
                "No texts to embed",
                details="Received empty texts list.",
            )

        try:
            logger.debug("Embedding %d texts with batch_size=%d", len(texts), self.batch_size)

            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            # Verify dimensions
            if embeddings.shape[1] != EMBEDDING_DIMENSION:
                logger.warning(
                    "Unexpected embedding dimension: got %d, expected %d",
                    embeddings.shape[1],
                    EMBEDDING_DIMENSION,
                )

            return embeddings

        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(
                "Failed to generate embeddings",
                details=str(e),
            ) from e

    def embed_chunks(
        self,
        chunks: list[Chunk],
        show_progress: bool = True,
    ) -> np.ndarray:
        """Generate embeddings for a list of chunks.

        This is the main method for embedding chunks during ingestion.
        It extracts text content from chunks and generates embeddings.

        Args:
            chunks: List of Chunk objects to embed.
            show_progress: Whether to show progress bar.

        Returns:
            NumPy array of shape (n_chunks, embedding_dim).

        Raises:
            EmbeddingError: If embedding generation fails.

        Example:
            >>> embeddings = generator.embed_chunks(chunks)
            >>> print(f"Shape: {embeddings.shape}")
        """
        if not chunks:
            raise EmbeddingError(
                "No chunks to embed",
                details="Received empty chunks list.",
            )

        filing_id = chunks[0].filing_id

        logger.info(
            "Embedding %d chunks from %s %s",
            len(chunks),
            filing_id.ticker,
            filing_id.form_type,
        )

        texts = [chunk.content for chunk in chunks]
        embeddings = self.embed_texts(texts, show_progress=show_progress)

        logger.info(
            "Generated embeddings: shape %s",
            embeddings.shape,
        )

        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Generate embedding for a search query.

        This method is optimised for single query embedding during search.
        It returns a 1D array suitable for ChromaDB query.

        Args:
            query: Search query text.

        Returns:
            NumPy array of shape (embedding_dim,).

        Raises:
            EmbeddingError: If query is empty or embedding fails.

        Example:
            >>> query_embedding = generator.embed_query("What are the risk factors?")
            >>> print(f"Shape: {query_embedding.shape}")
        """
        if not query or not query.strip():
            raise EmbeddingError(
                "Empty query",
                details="Cannot embed empty or whitespace-only query.",
            )

        logger.debug("Embedding query: %s...", query[:50])

        embeddings = self.embed_texts([query], show_progress=False)

        # Return as 1D array
        return embeddings[0]

    def embed_query_for_chromadb(self, query: str) -> list[list[float]]:
        """Generate embedding in ChromaDB query format.

        ChromaDB expects query_embeddings as list[list[float]].
        This method provides the correct format.

        Args:
            query: Search query text.

        Returns:
            List containing single embedding as list of floats.
        """
        embedding = self.embed_query(query)
        return [embedding.tolist()]
