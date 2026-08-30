import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel


# ============================================================
# Environment
# ============================================================

load_dotenv()

groq_api_key = os.getenv(
    "GROQ_API_KEY"
) or ""


# ============================================================
# Groq OpenAI-compatible client
# ============================================================

groq_client = AsyncOpenAI(
    api_key=(
        groq_api_key
        if groq_api_key
        else "not-configured"
    ),
    base_url="https://api.groq.com/openai/v1",
)


# ============================================================
# Reliability Agent model
# ============================================================

groq_model = OpenAIChatCompletionsModel(
    model="openai/gpt-oss-20b",
    openai_client=groq_client,
)