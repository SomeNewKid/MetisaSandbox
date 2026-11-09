"""Agent Memory tests for the sample agent."""

from __future__ import annotations

import json

import requests

from metisa_common.secrets_helper import (
    load_secrets,
)
from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from .._helper import (
    print_caution,
    print_disabled,
    print_elapsed_time,
    print_failure,
    print_success,
    print_suite_title,
)

_SKIP_AGENT_MEMORY_TESTS = False


def test_agent_memory(specification: MetisaSpecification):
    """Run code execution tests."""
    print_suite_title("Agent Memory")

    if _SKIP_AGENT_MEMORY_TESTS:
        print_caution("Agent memory capability is being skipped.")
        return

    if Capability.AGENT_MEMORY not in specification.capabilities:
        print_disabled("Agent memory capability not declared.")
        return

    episode_summary = "This is a summary of an episode"
    episode_id: str | None = None
    with print_elapsed_time():
        try:
            episode_id = _save_episode(episode_summary)
            if episode_id:
                print_success("Created episode ID:", episode_id)
            else:
                print_failure("Did not create episode.")
        except Exception as error:
            print_failure("Save episode error:", error)

    if episode_id:
        with print_elapsed_time():
            try:
                episode_details = _get_episode(episode_id)
                if episode_details:
                    episode_details_summary = episode_details.get("summary", None)
                    if episode_details_summary:
                        print_success("Retrieved episode:", episode_details_summary)
                    else:
                        print_failure("Did not retrieve episode details.")
                else:
                    print_failure("Did not retrieve episode.")
            except Exception as error:
                print_failure("Retrieve episode error:", error)
    else:
        print_caution("Skipping retrieve episode test.")

    if episode_id:
        with print_elapsed_time():
            try:
                was_deleted = _delete_episode(episode_id)
                if was_deleted:
                    print_success("Deleted episode:", episode_id)
                else:
                    print_failure("Did not delete episode.")
            except Exception as error:
                print_failure("Delete episode error:", error)
    else:
        print_caution("Skipping delete episode test.")

    if episode_id:
        with print_elapsed_time():
            try:
                episode_details = _get_episode(episode_id)
                if episode_details:
                    print_failure("Retrieved deleted episode.", episode_id)
                else:
                    print_success("Did not retrieve deleted episode.")
            except Exception as error:
                print_failure("Retrieve deleted episode error:", error)
    else:
        print_caution("Skipping re-retrieve episode test.")

    print(flush=True)
    favorite_color = "blue"
    memory_id: str | None = None
    with print_elapsed_time():
        try:
            memory_id = _save_memory(favorite_color)
            if memory_id:
                print_success("Created memory ID:", memory_id)
            else:
                print_failure("Did not create memory.")
        except Exception as error:
            print_failure("Save memory error:", error)

    if memory_id:
        with print_elapsed_time():
            try:
                memory_details = _get_memory(memory_id)
                if memory_details:
                    memory_details_fact = memory_details.get("fact", None)
                    memory_details_value = memory_details.get("value", None)
                    if memory_details_fact and memory_details_value:
                        if memory_details_value == favorite_color:
                            print_success(
                                "Retrieved memory:",
                                memory_details_fact,
                                memory_details_value,
                            )
                        else:
                            print_failure(
                                "Memory value does not match favorite color:",
                                memory_details_value,
                                favorite_color,
                            )
                    else:
                        print_failure("Did not retrieve memory details.")
                else:
                    print_failure("Did not retrieve memory.")
            except Exception as error:
                print_failure("Retrieve memory error:", error)
    else:
        print_caution("Skipping retrieve memory test.")

    favorite_color = "red"
    if memory_id:
        with print_elapsed_time():
            try:
                memory_id = _update_memory(memory_id, favorite_color)
                if memory_id:
                    print_success("Updated memory ID:", memory_id)
                else:
                    print_failure("Did not update memory.")
            except Exception as error:
                print_failure("Update memory error:", error)

    if memory_id:
        with print_elapsed_time():
            try:
                memory_details = _get_memory(memory_id)
                if memory_details:
                    memory_details_fact = memory_details.get("fact", None)
                    memory_details_value = memory_details.get("value", None)
                    if memory_details_fact and memory_details_value:
                        if memory_details_value == favorite_color:
                            print_success(
                                "Retrieved memory:",
                                memory_details_fact,
                                memory_details_value,
                            )
                        else:
                            print_failure(
                                "Memory value does not match favorite color:",
                                memory_details_value,
                                favorite_color,
                            )
                    else:
                        print_failure("Did not retrieve memory details.")
                else:
                    print_failure("Did not retrieve memory.")
            except Exception as error:
                print_failure("Retrieve memory error:", error)
    else:
        print_caution("Skipping retrieve memory test.")

    if memory_id:
        with print_elapsed_time():
            try:
                was_deleted = _delete_memory(memory_id)
                if was_deleted:
                    print_success("Deleted memory:", memory_id)
                else:
                    print_failure("Did not delete memory.")
            except Exception as error:
                print_failure("Delete memory error:", error)
    else:
        print_caution("Skipping delete memory test.")

    if memory_id:
        with print_elapsed_time():
            try:
                memory_details = _get_memory(memory_id)
                if memory_details:
                    print_failure("Retrieved deleted memory.", memory_id)
                else:
                    print_success("Did not retrieve deleted memory.")
            except Exception as error:
                print_failure("Retrieve deleted memory error:", error)
    else:
        print_caution("Skipping re-retrieve memory test.")


def _save_episode(
    episode_summary: str,
) -> str:
    if not episode_summary:
        raise ValueError("Episode summary is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = "http://metisa-agent-memory:8000/episodes"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }
    payload = {
        "kind": "summary",
        "agent_id": "sample_agent",
        "content": {"summary": episode_summary},
    }

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.post(
                agent_memory_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Agent memory did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Agent memory returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Agent memory returned JSON which could not be loaded.")

    identifier = result.get("id", None)

    if identifier is None:
        raise RuntimeError("Agent memory JSON response did not include 'id'.")
    if not isinstance(identifier, str):
        raise RuntimeError("Agent memory JSON 'id' was not a string.")

    return identifier


def _get_episode(
    episode_id: str,
) -> dict[str, str] | None:
    if not episode_id:
        raise ValueError("Episode ID is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = f"http://metisa-agent-memory:8000/episodes/{episode_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.get(
                agent_memory_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            if response.status_code == 404:  # Not found
                return None
            response.raise_for_status()
        if not content:
            raise RuntimeError("Agent memory did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Agent memory returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Agent memory returned JSON which could not be loaded.")

    identifier = result.get("id", None)

    if identifier is None:
        raise RuntimeError("Agent memory JSON response did not include 'id'.")
    if not isinstance(identifier, str):
        raise RuntimeError("Agent memory JSON 'id' was not a string.")

    if identifier != episode_id:
        error_message = (
            "Agent memory retrieved a different episode. "
            f"Requested '{episode_id}', "
            f"received '{identifier}', "
        )
        raise RuntimeError(error_message)

    content_json = result.get("content", None)

    if content_json is None:
        raise RuntimeError("Agent memory JSON response did not include 'content'.")
    if not isinstance(content_json, dict):
        raise RuntimeError("Agent memory JSON 'content' was not a dictionary.")

    summary = content_json.get("summary", None)
    if summary is None:
        raise RuntimeError("Agent memory JSON content did not include 'summary'.")
    if not isinstance(summary, str):
        raise RuntimeError("Agent memory JSON 'content.summary' was not a string.")

    return {
        "id": identifier,
        "summary": summary,
    }


def _delete_episode(
    episode_id: str,
) -> bool:
    if not episode_id:
        raise ValueError("Episode ID is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = f"http://metisa-agent-memory:8000/episodes/{episode_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }

    status_code: int | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.delete(
                agent_memory_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            response.raise_for_status()
            status_code = response.status_code
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    return status_code == 204  # No content


def _save_memory(
    favorite_color: str,
) -> str:
    if not favorite_color:
        raise ValueError("Favorite color is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = "http://metisa-agent-memory:8000/memories"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }
    payload = {
        "subject": "user_preferences",
        "content": {"fact": "favorite_color", "value": favorite_color},
        "text": f"The user's favorite color is {favorite_color}.",
        "embedding": [0.25, -0.5, 0.75],
    }

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.post(
                agent_memory_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Agent memory did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Agent memory returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Agent memory returned JSON which could not be loaded.")

    identifier = result.get("id", None)

    if identifier is None:
        raise RuntimeError("Agent memory JSON response did not include 'id'.")
    if not isinstance(identifier, str):
        raise RuntimeError("Agent memory JSON 'id' was not a string.")

    return identifier


def _update_memory(
    memory_id: str,
    favorite_color: str,
) -> str:
    if not memory_id:
        raise ValueError("Memory ID is required.")
    if not favorite_color:
        raise ValueError("Favorite color is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = f"http://metisa-agent-memory:8000/memories/{memory_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }
    payload = {
        "subject": "user_preferences",
        "content": {"fact": "favorite_color", "value": favorite_color},
        "text": f"The user's favorite color is {favorite_color}.",
        "embedding": [0.35, -0.4, 0.65],
    }

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.put(
                agent_memory_endpoint,
                json=payload,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            response.raise_for_status()
        if not content:
            raise RuntimeError("Agent memory did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Agent memory returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Agent memory returned JSON which could not be loaded.")

    identifier = result.get("id", None)

    if identifier is None:
        raise RuntimeError("Agent memory JSON response did not include 'id'.")
    if not isinstance(identifier, str):
        raise RuntimeError("Agent memory JSON 'id' was not a string.")

    return identifier


def _get_memory(
    memory_id: str,
) -> dict[str, str] | None:
    if not memory_id:
        raise ValueError("Episode ID is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = f"http://metisa-agent-memory:8000/memories/{memory_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }

    content: str | None = None
    result: dict[str, object] | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.get(
                agent_memory_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            content = response.text
            if response.status_code == 404:  # Not found
                return None
            response.raise_for_status()
        if not content:
            raise RuntimeError("Agent memory did not return any content.")
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError("Agent memory returned invalid JSON.") from error

    if result is None:
        raise RuntimeError("Agent memory returned JSON which could not be loaded.")

    identifier = result.get("id", None)

    if identifier is None:
        raise RuntimeError("Agent memory JSON response did not include 'id'.")
    if not isinstance(identifier, str):
        raise RuntimeError("Agent memory JSON 'id' was not a string.")

    if identifier != memory_id:
        error_message = (
            "Agent memory retrieved a different memory. "
            f"Requested '{memory_id}', "
            f"received '{identifier}', "
        )
        raise RuntimeError(error_message)

    content_json = result.get("content", None)

    if content_json is None:
        raise RuntimeError("Agent memory JSON response did not include 'content'.")
    if not isinstance(content_json, dict):
        raise RuntimeError("Agent memory JSON 'content' was not a dictionary.")

    fact = content_json.get("fact", None)
    if fact is None:
        raise RuntimeError("Agent memory JSON content did not include 'fact'.")
    if not isinstance(fact, str):
        raise RuntimeError("Agent memory JSON 'content.fact' was not a string.")

    value = content_json.get("value", None)
    if value is None:
        raise RuntimeError("Agent memory JSON content did not include 'value'.")
    if not isinstance(value, str):
        raise RuntimeError("Agent memory JSON 'content.value' was not a string.")

    return {
        "id": identifier,
        "fact": fact,
        "value": value,
    }


def _delete_memory(
    memory_id: str,
) -> bool:
    if not memory_id:
        raise ValueError("Episode ID is required.")

    secrets = load_secrets()
    agent_memory_token = secrets["METISA_AGENT_MEMORY_TOKEN"]
    if not agent_memory_token:
        raise RuntimeError("METISA_AGENT_MEMORY_TOKEN secret is not set.")

    agent_memory_endpoint = f"http://metisa-agent-memory:8000/memories/{memory_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {agent_memory_token}",
    }

    status_code: int | None = None

    try:
        with requests.Session() as session:
            session.trust_env = False  # do not use Squid
            response = session.delete(
                agent_memory_endpoint,
                headers=headers,
                timeout=(5, 240),
            )
            response.raise_for_status()
            status_code = response.status_code
    except Exception as error:
        raise RuntimeError(f"Agent memory returned an error: {error}") from error

    return status_code == 204  # No content
