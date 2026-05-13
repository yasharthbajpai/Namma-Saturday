"""AWS Bedrock client wrapper for Claude (Anthropic) models.

Exposes a single async-friendly `invoke_claude` function. boto3 is sync, so we
run it in a thread executor to keep FastAPI's event loop unblocked.
"""

import asyncio
import json
import boto3
from botocore.config import Config
from core.config import settings


class BedrockError(Exception):
    pass


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
        raise BedrockError("AWS credentials are not configured")

    _client = boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(retries={"max_attempts": 2, "mode": "standard"}, read_timeout=60),
    )
    return _client


def _invoke_sync(prompt: str, system: str | None, max_tokens: int) -> str:
    client = _get_client()
    body: dict = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    try:
        response = client.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
    except Exception as exc:
        raise BedrockError(f"Bedrock invoke failed: {exc}") from exc

    payload = json.loads(response["body"].read())
    parts = payload.get("content", [])
    if not parts:
        raise BedrockError("Bedrock returned empty content")
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text.strip()


async def invoke_claude(prompt: str, system: str | None = None, max_tokens: int = 2000) -> str:
    return await asyncio.to_thread(_invoke_sync, prompt, system, max_tokens)
