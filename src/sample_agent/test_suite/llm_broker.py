"""LLM Broker tests for the sample agent."""

from __future__ import annotations

import requests

from metisa_common.specification_models import (
    Capability,
    MetisaSpecification,
)

from .._helper import (
    print_caution,
    print_disabled,
    print_elapsed_time,
    print_failure,
    print_message,
    print_success,
    print_suite_title,
)

_SKIP_LLM_BROKER_TESTS = False


def test_llm_broker(specification: MetisaSpecification):
    """Run LLM Broker tests."""
    print_suite_title("LLM Broker")

    if _SKIP_LLM_BROKER_TESTS:
        print_caution("LLM Broker capability is being skipped.")
        return

    if Capability.LLM_BROKER not in specification.capabilities:
        print_disabled("LLM Broker capability not declared.")
        return

    prompt_for_llm = "Explain Docker networks in two sentences."

    if specification.llm_broker is not None:
        local_models = specification.llm_broker.local_models
    else:
        local_models = []

    if specification.llm_broker is not None:
        online_models = specification.llm_broker.online_models
    else:
        online_models = []

    granite_alias = "granite-4-1b"
    if granite_alias in local_models:
        with print_elapsed_time():
            try:
                print_message("To Granite:", prompt_for_llm)
                print(flush=True)
                llm_chat_completion = _get_granite_chat_completion(
                    granite_alias, prompt_for_llm
                )
                print_success("From Granite (chat completion):", llm_chat_completion)
            except Exception as error:
                print_failure("Granite chat error:", error)

        with print_elapsed_time():
            try:
                llm_response = _get_llm_response(granite_alias, prompt_for_llm)
                print_success("From Granite (response):", llm_response)
            except Exception as error:
                print_failure("Granite response error:", error)

    qwen_alias = "qwen-3-small"
    if qwen_alias in local_models:
        with print_elapsed_time():
            try:
                print()
                print_message("To Qwen:", prompt_for_llm)
                llm_chat_completion = _get_qwen_chat_completion(
                    "qwen-3-small", prompt_for_llm
                )
                print_success("From Qwen (chat completion):", llm_chat_completion)
            except Exception as error:
                print_failure("Qwen error:", error)

        with print_elapsed_time():
            try:
                print()
                llm_response = _get_llm_response("qwen-3-small", prompt_for_llm)
                print_success("From Qwen (response):", llm_response)
            except Exception as error:
                print_failure("Qwen response error:", error)

    gpt_alias = "gpt-4o"
    if gpt_alias in online_models:
        with print_elapsed_time():
            try:
                print()
                print_message("To GPT:", prompt_for_llm)
                print(flush=True)
                llm_chat_completion = _get_granite_chat_completion(
                    gpt_alias, prompt_for_llm
                )
                print_success("From GPT (chat completion):", llm_chat_completion)
            except Exception as error:
                print_failure("GPT chat error:", error)

        with print_elapsed_time():
            try:
                print()
                llm_response = _get_llm_response(gpt_alias, prompt_for_llm)
                print_success("From GPT (response):", llm_response)
            except Exception as error:
                print_failure("GPT response error:", error)


def _get_granite_chat_completion(
    llm_alias: str,
    prompt: str,
) -> str:
    with requests.Session() as session:
        # Private-network requests must bypass the internet proxy.
        session.trust_env = False

        try:
            response = session.post(
                "http://metisa-llm-broker:8000/v1/chat/completions",
                json={
                    "model": llm_alias,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "max_tokens": 128,
                    "stream": False,
                },
                timeout=(5, 600),
            )
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            return answer
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            raise RuntimeError(
                f"LLM request to '{llm_alias}' failed:", error
            ) from error


def _get_qwen_chat_completion(
    llm_alias: str,
    prompt: str,
) -> str:
    with requests.Session() as session:
        # Private-network requests must bypass the internet proxy.
        session.trust_env = False

        try:
            response = session.post(
                "http://metisa-llm-broker:8000/v1/chat/completions",
                json={
                    "model": llm_alias,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "chat_template_kwargs": {"enable_thinking": False},
                    "max_tokens": 128,
                    "stream": False,
                },
                timeout=(5, 600),
            )
            response.raise_for_status()
            result = response.json()

            choice = result["choices"][0]

            # print("Qwen message:", choice["message"])
            # print("Qwen finish reason:", choice.get("finish_reason"))
            # print("Qwen usage:", result.get("usage"))

            return choice["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            raise RuntimeError(
                f"LLM request to '{llm_alias}' failed:", error
            ) from error


def _get_llm_response(
    llm_alias: str,
    prompt: str,
) -> str:
    with requests.Session() as session:
        session.trust_env = False

        response = session.post(
            "http://metisa-llm-broker:8000/v1/responses",
            json={
                "model": llm_alias,
                "instructions": "Answer concisely.",
                "input": prompt,
                "max_output_tokens": 512,
                "stream": False,
                "store": False,
            },
            timeout=(5, 600),
        )

        response.raise_for_status()
        result = response.json()

    if result.get("object") != "response":
        raise RuntimeError("Unexpected response object type.")

    if result.get("model") != llm_alias:
        raise RuntimeError("Unexpected model alias.")

    if result.get("status") != "completed":
        status = result.get("status")
        details = result.get("incomplete_details")
        raise RuntimeError(f"Response status: {status}, details: {details}")

    text_parts: list[str] = []
    for item in result.get("output", []):
        if item.get("type") != "message":
            continue

        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content["text"])

        if not text_parts:
            raise RuntimeError("Response contained no output text.")

    return "\n".join(text_parts)
