import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise RuntimeError("GROQ_API_KEY is not configured")

groq_client = AsyncOpenAI(
    api_key=groq_api_key,
    base_url="https://api.groq.com/openai/v1",
)

groq_model = OpenAIChatCompletionsModel(
    model="openai/gpt-oss-20b",
    openai_client=groq_client,
)