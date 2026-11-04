"""Synchronous PostgreSQL access for episodes and memories."""

from __future__ import annotations

from collections.abc import Sequence
from typing import LiteralString
from uuid import UUID

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from ._models import Episode, Memory

_EPISODE_COLUMNS: LiteralString = """
    id, 
    namespace, 
    agent_id, 
    run_id, 
    trace_id, 
    kind,
    content, 
    metadata, 
    created_at, 
    expires_at
"""

# Psycopg converts PostgreSQL real[] into list[float].
# This keeps the model independent of NumPy and pgvector Python adapters.
_MEMORY_COLUMNS: LiteralString = """
    id, 
    namespace, 
    subject, 
    content, 
    text,
    embedding::real[] AS embedding,
    metadata, 
    valid_to, 
    created_at, 
    updated_at, 
    expires_at
"""


class MemoryStore:
    """Create, retrieve, update, and delete records within one namespace."""

    def __init__(
        self,
        connection_string: str,
        namespace: str,
    ) -> None:
        """Configure database access and the namespace used by every operation."""
        if not connection_string.strip():
            raise ValueError("connection_string is required.")
        if not namespace.strip():
            raise ValueError("namespace is required.")

        self._connection_string = connection_string
        self._namespace = namespace

    def create_episode(
        self,
        episode: Episode,
    ) -> Episode:
        """Insert an episode and return its database-generated values."""
        episode.validate()
        self._check_namespace(episode.namespace)

        if episode.id is not None or episode.created_at is not None:
            raise ValueError("The specified episode is not new.")

        query = f"""
            INSERT INTO public.episodes (
                namespace, 
                agent_id, 
                run_id, 
                trace_id, 
                kind,
                content, 
                metadata, 
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {_EPISODE_COLUMNS}
        """

        parameters = (
            episode.namespace,
            episode.agent_id,
            episode.run_id,
            episode.trace_id,
            episode.kind,
            Jsonb(episode.content),
            Jsonb(episode.metadata),
            episode.expires_at,
        )

        created = self._fetch_episode(query, parameters)
        if created is None:
            raise RuntimeError("Episode insertion returned no row.")

        return created

    def get_episode(
        self,
        episode_id: UUID,
    ) -> Episode | None:
        """Return an episode, or None if it does not exist in this namespace."""
        identifier = self._require_id(episode_id)

        query = f"""
            SELECT {_EPISODE_COLUMNS}
            FROM public.episodes
            WHERE id = %s AND namespace = %s
        """

        parameters = (
            identifier,
            self._namespace,
        )

        return self._fetch_episode(query, parameters)

    def delete_episode(
        self,
        episode_id: UUID,
    ) -> bool:
        """Delete an episode; return False if no matching row exists."""
        identifier = self._require_id(episode_id)

        query = """
            DELETE FROM public.episodes
            WHERE id = %s AND namespace = %s
            RETURNING id
        """

        parameters = (
            identifier,
            self._namespace,
        )

        return self._delete(query, parameters)

    def create_memory(
        self,
        memory: Memory,
    ) -> Memory:
        """Insert a memory and return its database-generated values."""
        memory.validate()
        self._check_namespace(memory.namespace)

        if (
            memory.id is not None
            or memory.created_at is not None
            or memory.updated_at is not None
        ):
            raise ValueError("The specified memory is not new.")

        query = f"""
            INSERT INTO public.memories (
                namespace, 
                subject, 
                content, 
                text,
                embedding, 
                metadata, 
                valid_to, 
                expires_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s::real[]::vector, %s, %s, %s
            )
            RETURNING {_MEMORY_COLUMNS}
        """

        embedding = [float(value) for value in memory.embedding]

        parameters = (
            memory.namespace,
            memory.subject,
            Jsonb(memory.content),
            memory.text,
            embedding,
            Jsonb(memory.metadata),
            memory.valid_to,
            memory.expires_at,
        )

        created = self._fetch_memory(query, parameters)
        if created is None:
            raise RuntimeError("Memory insertion returned no row.")

        return created

    def get_memory(
        self,
        memory_id: UUID,
    ) -> Memory | None:
        """Return a memory, or None if it does not exist in this namespace."""
        identifier = self._require_id(memory_id)

        query = f"""
            SELECT {_MEMORY_COLUMNS}
            FROM public.memories
            WHERE id = %s AND namespace = %s
        """

        parameters = (
            identifier,
            self._namespace,
        )

        return self._fetch_memory(query, parameters)

    def update_memory(
        self,
        memory: Memory,
    ) -> Memory:
        """Replace editable fields and assign updated_at in PostgreSQL."""
        memory.validate()
        self._check_namespace(memory.namespace)
        identifier = self._require_id(memory.id)

        query = f"""
            UPDATE public.memories
            SET subject = %s,
                content = %s,
                text = %s,
                embedding = %s::real[]::vector,
                metadata = %s,
                valid_to = %s,
                expires_at = %s,
                updated_at = statement_timestamp()
            WHERE id = %s AND namespace = %s
            RETURNING {_MEMORY_COLUMNS}
        """

        embedding = [float(value) for value in memory.embedding]

        parameters = (
            memory.subject,
            Jsonb(memory.content),
            memory.text,
            embedding,
            Jsonb(memory.metadata),
            memory.valid_to,
            memory.expires_at,
            identifier,
            self._namespace,
        )

        updated = self._fetch_memory(query, parameters)
        if updated is None:
            raise LookupError(f"Memory {identifier} was not found in this namespace.")

        return updated

    def delete_memory(
        self,
        memory_id: UUID,
    ) -> bool:
        """Delete a memory; return False if no matching row exists."""
        identifier = self._require_id(memory_id)

        query = """
            DELETE FROM public.memories
            WHERE id = %s AND namespace = %s
            RETURNING id
        """

        parameters = (
            identifier,
            self._namespace,
        )

        return self._delete(query, parameters)

    def _fetch_episode(
        self,
        query: LiteralString,
        parameters: Sequence[object],
    ) -> Episode | None:
        with psycopg.connect(self._connection_string, connect_timeout=10) as connection:
            with connection.cursor(row_factory=class_row(Episode)) as cursor:
                cursor.execute(query, parameters)
                episode = cursor.fetchone()

                if episode is not None:
                    episode.validate()

        # The connection context commits before reaching this return.
        return episode

    def _fetch_memory(
        self,
        query: LiteralString,
        parameters: Sequence[object],
    ) -> Memory | None:
        with psycopg.connect(self._connection_string, connect_timeout=10) as connection:
            with connection.cursor(row_factory=class_row(Memory)) as cursor:
                cursor.execute(query, parameters)
                memory = cursor.fetchone()

                if memory is not None:
                    memory.validate()

        # The connection context commits before reaching this return.
        return memory

    def _delete(self, query: LiteralString, parameters: Sequence[object]) -> bool:
        with psycopg.connect(self._connection_string, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                deleted = cursor.fetchone() is not None

        return deleted

    def _check_namespace(
        self,
        namespace: str,
    ) -> None:
        if namespace != self._namespace:
            raise ValueError("The record namespace must match the store namespace.")

    def _require_id(
        self,
        identifier: UUID | None,
    ) -> UUID:
        if identifier is None:
            raise ValueError("This operation requires a record ID.")

        return identifier
