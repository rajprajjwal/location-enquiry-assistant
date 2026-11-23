"""
Shared factory for ChatOpenAI (remote vLLM) and FastEmbedEmbeddings (local ONNX).

The vLLM server at https://103.42.50.41:1031/v1 does NOT expose /v1/embeddings,
so embeddings run fully locally via fastembed (ONNX runtime, no torch, no GPU).

SSL_VERIFY=false  → skips TLS verification (Caddy self-signed ECDSA cert)
SSL_VERIFY=true   → uses vm07-ca.crt (requires OS trust store import)
"""
import os
import httpx
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import FastEmbedEmbeddings

_EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


def _ssl_verify():
    val = os.getenv("SSL_VERIFY", "false").lower()
    if val == "false":
        return False
    cert = os.path.abspath(os.getenv("SSL_CERT_PATH", "./vm07-ca.crt"))
    return cert if os.path.exists(cert) else False


def _http_client() -> httpx.Client:
    return httpx.Client(verify=_ssl_verify())


def _async_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=_ssl_verify())


def get_llm(temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-8B"),
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://103.42.50.41:1031/v1"),
        http_client=_http_client(),
        http_async_client=_async_http_client(),
    )


_embeddings = None


def get_embeddings() -> FastEmbedEmbeddings:
    """Local ONNX embeddings — downloads ~25MB model on first call, cached after."""
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings(model_name=_EMBED_MODEL)
    return _embeddings
