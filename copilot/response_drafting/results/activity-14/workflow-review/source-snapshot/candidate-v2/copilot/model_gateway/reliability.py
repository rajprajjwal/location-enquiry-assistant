"""Shared enquiry limits, retry credits and execution deadlines."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from functools import lru_cache, wraps
from pathlib import Path
from threading import Lock, Event
import time

from pydantic import BaseModel, ConfigDict, Field
import yaml

from copilot.paths import CONFIG_DIR


class ReliabilityError(RuntimeError):
    pass


class DeadlineExceeded(ReliabilityError):
    pass


class RetryLimitExceeded(ReliabilityError):
    pass


class QueryBudgetExceeded(ReliabilityError):
    pass


class ToolTimeout(ReliabilityError):
    pass


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    max_retries_per_step: int = Field(default=2, ge=0, le=2)
    enquiry_timeout_seconds: float = Field(default=120, gt=0)
    model_timeout_seconds: float = Field(default=30, gt=0)
    tool_timeout_seconds: float = Field(default=15, gt=0)
    token_budget: int = Field(default=32768, gt=0)


@lru_cache(maxsize=1)
def configured_limits():
    return Limits.model_validate(yaml.safe_load((CONFIG_DIR / "reliability.yaml").read_text()))


_CURRENT = ContextVar("reliability_query", default=None)
_PHASE = ContextVar("reliability_step", default="enquiry")
_TOOL_CANCELLATIONS = ContextVar("tool_cancellations", default=())


@dataclass
class QuerySession:
    limits: Limits
    clock: object = time.monotonic
    sleeper: object = None
    reserved_tokens: int = 0
    observed_tokens: int = 0
    model_attempts: int = 0
    retries: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    lock: object = field(default_factory=Lock)
    started: float = field(init=False)

    def __post_init__(self):
        self.started = self.clock()

    def event(self, kind, **details):
        with self.lock:
            self.events.append({"kind": kind, "step": _PHASE.get(), **details})

    def remaining(self):
        return max(0, self.limits.enquiry_timeout_seconds - (self.clock() - self.started))

    def check(self):
        if any(event.is_set() for event in _TOOL_CANCELLATIONS.get()):
            raise ToolTimeout("Tool wait expired; further worker calls are blocked.")
        if self.remaining() <= 0:
            self.event("query_timeout")
            raise DeadlineExceeded("Enquiry deadline reached.")

    def retry(self):
        self.check()
        step = _PHASE.get()
        with self.lock:
            count = self.retries.get(step, 0)
            if count >= self.limits.max_retries_per_step:
                self.events.append({"kind": "retry_limit", "step": step})
                raise RetryLimitExceeded("Retry limit reached for this step.")
            self.retries[step] = count + 1
            self.events.append({"kind": "retry", "step": step, "retry": count + 1})

    def retry_allowance(self):
        with self.lock:
            return max(0, self.limits.max_retries_per_step - self.retries.get(_PHASE.get(), 0))

    def reserve(self, tokens):
        self.check()
        with self.lock:
            if self.reserved_tokens + tokens > self.limits.token_budget:
                self.events.append({"kind": "token_budget", "step": _PHASE.get()})
                raise QueryBudgetExceeded("Enquiry token budget reached.")
            self.reserved_tokens += tokens
            self.model_attempts += 1

    def pause(self, seconds):
        self.check()
        if seconds >= self.remaining():
            self.event("query_timeout")
            raise DeadlineExceeded("Retry delay exceeds the enquiry deadline.")
        (self.sleeper or time.sleep)(seconds)
        self.check()

    def snapshot(self):
        with self.lock:
            return {
                "limits": self.limits.model_dump(), "reserved_tokens": self.reserved_tokens,
                "observed_tokens": self.observed_tokens, "model_attempts": self.model_attempts,
                "retries_by_step": dict(self.retries), "events": list(self.events),
                "elapsed_ms": round((self.clock() - self.started) * 1000),
            }


def active_query():
    return _CURRENT.get()


@contextmanager
def query_session(limits=None, *, clock=time.monotonic, sleeper=None):
    existing = active_query()
    if existing is not None:
        yield existing
        return
    session = QuerySession(limits or configured_limits(), clock=clock, sleeper=sleeper)
    token = _CURRENT.set(session)
    try:
        yield session
    finally:
        _CURRENT.reset(token)


@contextmanager
def step_scope(name):
    token = _PHASE.set(name)
    try:
        yield
    finally:
        _PHASE.reset(token)


@contextmanager
def bind_query(session):
    token = _CURRENT.set(session)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def query_scope(phase=None, *, attach=False):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            with query_session() as session:
                with step_scope(phase or _PHASE.get()):
                    result = function(*args, **kwargs)
                if attach:
                    result["reliability"] = session.snapshot()
                return result
        return run
    return decorate


def bounded_tool(function, arguments):
    """Discard late results from the registered read-only/proposal executors."""
    session = active_query()
    session.check()
    timeout = min(session.remaining(), session.limits.tool_timeout_seconds)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="copilot-tool")
    context = copy_context()
    cancelled = Event()
    def run():
        token = _TOOL_CANCELLATIONS.set((*_TOOL_CANCELLATIONS.get(), cancelled))
        try:
            return function(arguments)
        finally:
            _TOOL_CANCELLATIONS.reset(token)
    future = executor.submit(context.run, run)
    try:
        result = future.result(timeout=timeout)
        session.check()
        return result
    except FutureTimeout:
        cancelled.set()
        session.event("tool_timeout")
        future.cancel()
        raise ToolTimeout("Tool call timed out.") from None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
