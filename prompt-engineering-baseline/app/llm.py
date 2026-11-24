# Source history: Raj Kumar (a3ef3a6); shared-gateway integration recorded in source-history.json.
"""Adapt the isolated baseline's message interface to the project's shared client."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from copilot.model_gateway.client import LLMClient


class SharedChatModel:
    def __init__(self, temperature=0):
        self.temperature = temperature

    def invoke(self, messages, **kwargs):
        roles = {'human':'user', 'ai':'assistant', 'system':'system', 'tool':'tool'}
        converted = []
        for message in messages:
            if isinstance(message, dict):
                converted.append(dict(message))
            else:
                item = {'role':roles[message.type], 'content':message.content}
                if getattr(message, 'tool_call_id', None):
                    item['tool_call_id'] = message.tool_call_id
                converted.append(item)
        response = LLMClient().complete(converted, temperature=self.temperature,
            max_tokens=kwargs.pop('max_tokens', int(os.getenv('BASELINE_MAX_TOKENS', '1024'))), **kwargs)
        return SimpleNamespace(content=response.text, response_metadata={
            'token_usage':response.usage, 'finish_reason':response.finish_reason,
            'model_name':response.model, 'latency_ms':response.latency_ms})


def get_llm(temperature=0):
    return SharedChatModel(temperature)


_embeddings = None


def get_embeddings():
    """Load optional demo retrieval dependencies only when retrieval is used."""
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import FastEmbedEmbeddings
        _embeddings = FastEmbedEmbeddings(model_name=os.getenv('EMBED_MODEL', 'BAAI/bge-small-en-v1.5'))
    return _embeddings
