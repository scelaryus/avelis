"""LLM client configuration for all GFI agents.
Uses OpenRouter API with Claude via langchain-openai."""
from langchain_openai import ChatOpenAI

OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "anthropic/claude-sonnet-4"

def get_llm(temperature: float = 0.0, max_tokens: int = 2000) -> ChatOpenAI:
    """Get a configured LLM instance for any agent."""
    return ChatOpenAI(
        model=MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )
