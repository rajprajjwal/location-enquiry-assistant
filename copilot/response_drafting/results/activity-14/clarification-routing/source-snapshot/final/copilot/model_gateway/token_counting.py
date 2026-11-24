"""Count Qwen3 prompts using the model's published tokenizer and chat template."""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import os

from jinja2.sandbox import ImmutableSandboxedEnvironment
from tokenizers import Tokenizer
from .prepare_tokenizer import ASSETS


@lru_cache(maxsize=1)
def _resources():
    folder = Path(os.environ.get("TRACKB_TOKENIZER_DIR", Path(__file__).parent / "assets/qwen3-8b"))
    for name, expected in ASSETS.items():
        if not (folder / name).is_file() or hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Tokenizer assets are missing or do not match the pinned version")
    try:
        tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
    except Exception as exc:
        raise ValueError("Tokenizer assets are missing or invalid") from exc
    config = json.loads((folder / "tokenizer_config.json").read_text())
    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True,
                                               extensions=["jinja2.ext.loopcontrols"])
    environment.filters["tojson"] = lambda value, **kwargs: json.dumps(value, ensure_ascii=False, **kwargs)
    def raise_exception(message):
        raise ValueError(message)
    environment.globals["raise_exception"] = raise_exception
    return tokenizer, environment.from_string(config["chat_template"])


def count_text(text):
    return len(_resources()[0].encode(text, add_special_tokens=False).ids)


def native_prompt_tokens(messages, *, tools=None, thinking=False):
    tokenizer, template = _resources()
    try:
        text = template.render(messages=messages, tools=tools, add_generation_prompt=True,
                               enable_thinking=thinking)
    except (TypeError, ValueError) as exc:
        raise ValueError("Messages cannot be rendered by the Qwen chat template") from exc
    return len(tokenizer.encode(text, add_special_tokens=False).ids)


def count_metadata(messages, extra):
    metadata = [{key: value for key, value in message.items() if key not in {"role", "content"}}
                for message in messages]
    return count_text(json.dumps({"message_metadata": metadata,
                                 "response_format": extra.get("response_format"),
                                 "tool_choice": extra.get("tool_choice")}, ensure_ascii=False, sort_keys=True))


# The institute probe reports one framing token beyond the published template.
PROVIDER_FRAMING_TOKENS = 1


def count_prompt(messages, *, tools=None, thinking=False):
    return native_prompt_tokens(messages, tools=tools, thinking=thinking) + PROVIDER_FRAMING_TOKENS
