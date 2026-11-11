"""Search functions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from threading import Lock
from uuid import NAMESPACE_URL, uuid5

import requests
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from metisa_common.utilities.type_models import sanitize_content

_DOCUMENT_COLLECTION = "document_chunks"
_MANIFEST_COLLECTION = "document_manifests"
_INGESTION_LOCK = Lock()

# The following _MINIMUM_SCORE is an initial value based on a single query test.
# Real-world queries against real-world documents would demand either a more
# considered minimum score, or perhaps a document-specific minimum scores.
_MINIMUM_SCORE: float | None = 0.6

_KEYWORD_PAGE_SIZE = 100
_MAX_KEYWORD_LENGTH = 256


@dataclass(frozen=True)
class ChunkEmbedding:
    index: int
    text: str
    vector: list[float]


def get_keyword_chunks_from_document(
    filename: str,
    query: str,
    all_words: bool,
    metisa_json: dict[str, object],
) -> list[str]:
    sanitized_query = sanitize_content(query)
    if not sanitized_query.strip():
        raise ValueError("Query is required.")

    words = re.findall(r"[^\W_]+", sanitized_query)
    if not words:
        raise ValueError("Query must contain at least one searchable word.")

    for word in words:
        if len(word) > _MAX_KEYWORD_LENGTH:
            raise ValueError(
                f"Query words must not exceed {_MAX_KEYWORD_LENGTH} characters."
            )

    prepared = _prepare_document_index(filename, metisa_json)
    if prepared is None:
        return []

    model_name, _ = prepared

    return _query_keyword_chunks(
        filename=filename,
        words=words,
        all_words=all_words,
        model_name=model_name,
    )


def get_semantic_chunks_from_document(
    filename: str,
    prompt: str,
    metisa_json: dict[str, object],
) -> list[str]:
    sanitized_prompt = sanitize_content(prompt)
    if not sanitized_prompt.strip():
        raise ValueError("Prompt is required.")

    prepared = _prepare_document_index(filename, metisa_json)
    if prepared is None:
        return []

    model_name, embedding_model = prepared

    matching_chunks: list[str] = []

    hits = _query_matching_chunks(
        filename=filename,
        prompt=sanitized_prompt,
        embedding_model=embedding_model,
        model_name=model_name,
        limit=5,
        score_threshold=_MINIMUM_SCORE,
    )

    for hit in hits:
        text = _get_chunk_text(hit.payload)
        if text.strip():
            matching_chunks.append(text)

    return matching_chunks


def _prepare_document_index(
    filename: str,
    metisa_json: dict[str, object],
) -> tuple[str, TextEmbedding] | None:
    """Prepare the shared document index, or return None for no chunks."""
    if not filename:
        raise ValueError("Filename is required.")

    model_name = metisa_json.get("embedding_model", None)
    if model_name is None:
        raise ValueError("Metisa JSON file did not provide an embedding model.")
    if not isinstance(model_name, str):
        raise ValueError("Metisa JSON file provided a non-string embedding model.")
    model_name = model_name.strip()
    if not model_name:
        raise ValueError("Metisa JSON file provided an empty embedding model.")

    embedding_model = TextEmbedding(
        model_name=model_name,
        cache_dir="/models/fastembed",
        local_files_only=True,
        threads=1,
    )

    indexed = _ensure_document_indexed(
        filename=filename,
        model_name=model_name,
        embedding_model=embedding_model,
    )
    if not indexed:
        return None

    return model_name, embedding_model


def _ensure_document_indexed(
    filename: str,
    model_name: str,
    embedding_model: TextEmbedding,
) -> bool:
    identity = json.dumps(
        [filename, model_name],
        ensure_ascii=True,
        separators=(",", ";"),
    )
    manifest_uuid = uuid5(NAMESPACE_URL, identity)
    manifest_id = str(manifest_uuid)

    with _INGESTION_LOCK:
        client = QdrantClient(
            url="http://metisa-qdrant:6333",
            prefer_grpc=False,
            timeout=30,
            trust_env=False,
        )

        try:
            exists = client.collection_exists(
                collection_name=_MANIFEST_COLLECTION,
            )

            if not exists:
                # Metadata-only points: no embedding vectors.
                client.create_collection(
                    collection_name=_MANIFEST_COLLECTION,
                    vectors_config={},
                )

            records = client.retrieve(
                collection_name=_MANIFEST_COLLECTION,
                ids=[manifest_id],
                with_payload=True,
                with_vectors=False,
            )

            if records:
                payload = records[0].payload or {}
                if payload.get("status") == "complete":
                    _ensure_full_text_index(client)
                    return True

            chunks = _get_all_chunks(filename)
            if not chunks:
                return False

            embeddings = _embed_chunks(chunks, embedding_model)
            _save_embeddings(filename, model_name, embeddings)
            _ensure_full_text_index(client)

            manifest_payload = {
                "filename": filename,
                "embedding_model": model_name,
                "status": "complete",
            }
            manifest = models.PointStruct(
                id=manifest_id,
                vector={},
                payload=manifest_payload,
            )

            client.upsert(
                collection_name=_MANIFEST_COLLECTION,
                points=[manifest],
                wait=True,
            )

            return True
        finally:
            client.close()


def _ensure_full_text_index(
    client: QdrantClient,
) -> None:
    """Ensure chunk text has the expected full-text payload index."""
    collection = client.get_collection(
        collection_name=_DOCUMENT_COLLECTION,
    )
    existing_index = collection.payload_schema.get("text")

    if existing_index is not None:
        if existing_index.data_type != models.PayloadSchemaType.TEXT:
            raise ValueError("Chunk text has an incompatible payload index.")

        parameters = existing_index.params
        if not isinstance(parameters, models.TextIndexParams):
            raise ValueError("Chunk text index has no valid text parameters.")

        compatible = (
            parameters.tokenizer == models.TokenizerType.WORD
            and parameters.lowercase is True
            and parameters.min_token_len == 1
            and parameters.max_token_len == _MAX_KEYWORD_LENGTH
            and parameters.stemmer is None
            and parameters.stopwords is None
        )
        if not compatible:
            raise ValueError(
                "Chunk text index configuration does not match keyword search."
            )

        return

    parameters = models.TextIndexParams(
        type=models.TextIndexType.TEXT,
        tokenizer=models.TokenizerType.WORD,
        lowercase=True,
        min_token_len=1,
        max_token_len=_MAX_KEYWORD_LENGTH,
    )

    client.create_payload_index(
        collection_name=_DOCUMENT_COLLECTION,
        field_name="text",
        field_schema=parameters,
        wait=True,
    )


def _get_all_chunks(
    filename: str,
) -> list[str]:
    if not filename:
        raise ValueError("Filename is required.")

    docling_endpoint = "http://metisa-docling:8000/get-chunks-from-document"
    headers = {
        "Accept": "application/json",
    }
    payload = {"filename": filename}

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.post(
                docling_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Docling did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Docling returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Docling returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Docling returned JSON which could not be loaded.")

    chunks = result.get("chunks", None)

    if chunks is None:
        raise RuntimeError("Docling JSON response did not include 'chunks'.")
    if not isinstance(chunks, list):
        raise RuntimeError("Docling JSON 'chunks' was not a list.")

    sanitized_chunks: list[str] = []

    for chunk in chunks:
        if not isinstance(chunk, str):
            raise RuntimeError("Docling JSON 'chunks' list contained non-string items.")
        sanitized_chunk = sanitize_content(chunk)
        if not sanitized_chunk.strip():
            continue
        sanitized_chunks.append(sanitized_chunk)

    return sanitized_chunks


def _embed_chunks(
    chunks: list[str],
    embedding_model: TextEmbedding,
) -> list[ChunkEmbedding]:
    if not chunks:
        return []

    embedded_chunks: list[ChunkEmbedding] = []

    embeddings = embedding_model.passage_embed(
        chunks,
        batch_size=16,
        parallel=None,
    )

    chunk_pairs = zip(chunks, embeddings, strict=True)
    for chunk_index, (chunk_text, embedding) in enumerate(chunk_pairs):
        emdedded_chunk = ChunkEmbedding(
            index=chunk_index, text=chunk_text, vector=embedding.tolist()
        )
        embedded_chunks.append(emdedded_chunk)

    return embedded_chunks


def _save_embeddings(
    filename: str,
    model_name: str,
    embeddings: list[ChunkEmbedding],
) -> None:
    if not embeddings:
        return

    vector_size = len(embeddings[0].vector)

    client = QdrantClient(
        url="http://metisa-qdrant:6333",
        prefer_grpc=False,
        timeout=30,
        trust_env=False,  # avoid Squid
    )

    try:
        exists = client.collection_exists(
            collection_name=_DOCUMENT_COLLECTION,
        )

        if not exists:
            vector_config = models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            )
            client.create_collection(
                collection_name=_DOCUMENT_COLLECTION,
                vectors_config=vector_config,
            )

        collection = client.get_collection(collection_name=_DOCUMENT_COLLECTION)
        vectors = collection.config.params.vectors

        if not isinstance(vectors, models.VectorParams):
            raise ValueError("Expected a single unnamed vector configuration.")

        if vectors.size != vector_size:
            raise ValueError("Collection vector size does not match embeddings.")

        if vectors.distance != models.Distance.COSINE:
            raise ValueError("Collection must use cosine distance.")

        points: list[models.PointStruct] = []

        for embedding in embeddings:
            identity = json.dumps(
                [filename, model_name, embedding.index],
                ensure_ascii=True,
                separators=(",", ":"),
            )
            point_uuid = uuid5(NAMESPACE_URL, identity)

            payload = {
                "filename": filename,
                "embedding_model": model_name,
                "chunk_index": embedding.index,
                "text": embedding.text,
            }

            point = models.PointStruct(
                id=str(point_uuid),
                vector=embedding.vector,
                payload=payload,
            )
            points.append(point)

        client.upsert(
            collection_name=_DOCUMENT_COLLECTION,
            points=points,
            wait=True,
        )
    finally:
        client.close()


def _query_matching_chunks(
    filename: str,
    prompt: str,
    embedding_model: TextEmbedding,
    model_name: str,
    limit: int = 5,
    score_threshold: float | None = None,
) -> list[models.ScoredPoint]:
    if not prompt.strip():
        raise ValueError("Prompt is required.")

    if limit <= 0:
        raise ValueError("Limit must be positive.")

    query_embeddings = embedding_model.query_embed(prompt)
    query_embedding = next(iter(query_embeddings))
    query_vector = query_embedding.tolist()

    filename_condition = models.FieldCondition(
        key="filename",
        match=models.MatchValue(value=filename),
    )
    model_condition = models.FieldCondition(
        key="embedding_model",
        match=models.MatchValue(value=model_name),
    )
    document_filter = models.Filter(
        must=[
            filename_condition,
            model_condition,
        ]
    )

    client = QdrantClient(
        url="http://metisa-qdrant:6333",
        prefer_grpc=False,
        timeout=30,
        trust_env=False,  # avoid Squid
    )

    try:
        response = client.query_points(
            collection_name=_DOCUMENT_COLLECTION,
            query=query_vector,
            query_filter=document_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        return response.points
    finally:
        client.close()


def _query_keyword_chunks(
    filename: str,
    words: list[str],
    all_words: bool,
    model_name: str,
) -> list[str]:
    """Fetch every keyword-matching chunk from Qdrant."""
    if not words:
        raise ValueError("At least one keyword is required.")

    filename_condition = models.FieldCondition(
        key="filename",
        match=models.MatchValue(value=filename),
    )
    model_condition = models.FieldCondition(
        key="embedding_model",
        match=models.MatchValue(value=model_name),
    )

    word_conditions: list[models.Condition] = []

    for word in words:
        condition = models.FieldCondition(
            key="text",
            match=models.MatchText(text=word),
        )
        word_conditions.append(condition)

    if all_words:
        word_filter = models.Filter(must=word_conditions)
    else:
        word_filter = models.Filter(should=word_conditions)

    document_filter = models.Filter(
        must=[
            filename_condition,
            model_condition,
            word_filter,
        ],
    )

    client = QdrantClient(
        url="http://metisa-qdrant:6333",
        prefer_grpc=False,
        timeout=30,
        trust_env=False,
    )

    matching_chunks: list[tuple[int, str]] = []
    offset = None

    try:
        while True:
            records, next_offset = client.scroll(
                collection_name=_DOCUMENT_COLLECTION,
                scroll_filter=document_filter,
                limit=_KEYWORD_PAGE_SIZE,
                offset=offset,
                with_payload=["chunk_index", "text"],
                with_vectors=False,
            )

            for record in records:
                payload = record.payload
                text = _get_chunk_text(payload)

                if not text.strip():
                    continue

                # _get_chunk_text() already rejects a missing payload.
                if payload is None:
                    raise RuntimeError("Matching point has no payload.")

                chunk_index = payload.get("chunk_index")
                if not isinstance(chunk_index, int):
                    raise RuntimeError("Matching point has no valid chunk index.")

                matching_chunks.append((chunk_index, text))

            if next_offset is None:
                break

            offset = next_offset
    finally:
        client.close()

    # Scroll pages arrive in point-ID order, not document order.
    matching_chunks.sort(key=lambda item: item[0])

    return [text for _, text in matching_chunks]


def _get_chunk_text(
    payload: dict[str, object] | None,
) -> str:
    """Extract and sanitize chunk text from a Qdrant payload."""
    if payload is None:
        raise RuntimeError("Matching point has no payload.")

    text = payload.get("text")
    if not isinstance(text, str):
        raise RuntimeError("Matching point has no valid chunk text.")

    return sanitize_content(text)
