"""Shared LangChain/LangGraph runtime for JSON-based AI agents."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import get_settings


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content)


@lru_cache(maxsize=1)
def _build_json_agent_graph():
    from typing import TypedDict

    from langgraph.graph import END, StateGraph

    class JsonAgentState(TypedDict, total=False):
        system_prompt: str
        user_prompt: str
        temperature: float
        max_tokens: int
        raw_response: str
        parsed_json: dict[str, Any]
        ai_model: str
        # Optional vision fields (base64-encoded image)
        image_b64: str
        image_mime: str

    async def call_model(state: JsonAgentState) -> JsonAgentState:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        settings = get_settings()
        default_headers = None
        if settings.LLM_API_BASE and "openrouter.ai" in settings.LLM_API_BASE:
            default_headers = {
                "HTTP-Referer": "http://localhost",
                "X-Title": "GFI Platform",
            }

        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            temperature=state.get("temperature", settings.LLM_TEMPERATURE),
            max_tokens=state.get("max_tokens", settings.LLM_MAX_TOKENS),
            default_headers=default_headers,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        # Build HumanMessage — multimodal if image_b64 is present
        image_b64 = state.get("image_b64")
        image_mime = state.get("image_mime", "image/jpeg")
        if image_b64:
            human_content: list[dict[str, Any]] = [
                {"type": "text", "text": state["user_prompt"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime};base64,{image_b64}",
                    },
                },
            ]
            human_msg = HumanMessage(content=human_content)
        else:
            human_msg = HumanMessage(content=state["user_prompt"])

        response = await llm.ainvoke([
            SystemMessage(content=state["system_prompt"]),
            human_msg,
        ])
        return {
            "raw_response": _normalize_message_content(response.content),
            "ai_model": settings.LLM_MODEL,
        }

    def parse_json(state: JsonAgentState) -> JsonAgentState:
        return {"parsed_json": json.loads(state["raw_response"])}

    graph = StateGraph(JsonAgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("parse_json", parse_json)
    graph.set_entry_point("call_model")
    graph.add_edge("call_model", "parse_json")
    graph.add_edge("parse_json", END)
    return graph.compile()


async def invoke_json_agent(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")

    graph = _build_json_agent_graph()
    invoke_state: dict[str, Any] = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
        "max_tokens": settings.LLM_MAX_TOKENS if max_tokens is None else max_tokens,
    }
    if image_b64:
        invoke_state["image_b64"] = image_b64
        invoke_state["image_mime"] = image_mime or "image/jpeg"

    result = await graph.ainvoke(invoke_state)
    return {
        "parsed_json": result["parsed_json"],
        "raw_response": result.get("raw_response", ""),
        "ai_model": result.get("ai_model", settings.LLM_MODEL),
    }