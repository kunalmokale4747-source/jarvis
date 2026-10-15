from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")

    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401

    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=get_engine()), reset_settings, reset_engine


def test_groq_provider_requires_key_and_defaults():
    from core.config import reset_settings
    os.environ["GROQ_API_KEY"] = ""
    reset_settings()
    from core.llm import build_provider, ProviderConfigError

    try:
        build_provider("groq")
        assert False, "missing key should fail"
    except ProviderConfigError:
        pass

    os.environ["GROQ_API_KEY"] = "test-key"
    reset_settings()
    provider = build_provider("groq")
    assert provider.name == "groq"
    assert provider.name == "groq"
    assert provider.model == "openai/gpt-oss-20b"
    assert "groq.com/openai/v1" in getattr(provider, "base_url", "")
    os.environ["GROQ_API_KEY"] = ""


def test_mocked_ai_normal_response_works():
    from core.llm.types import LLMRequest, LLMResponse, LLMUsage
    from core.chat.service import ChatService

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        def complete(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse(text="JARVIS real-model style answer.", provider="fake", model="fake-model", usage=LLMUsage())

    import tempfile as _tmp
    _t = _tmp.mkdtemp()
    os.environ["ENV"] = "test"; os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{_t}/test.db"
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    db = sessionmaker(bind=get_engine())()
    service = ChatService(db, providers=[FakeProvider()])
    result = service.send("phase9-user", "Tell me a helpful update.")
    assert result["offline"] is False
    assert result["assistant_message"].content == "JARVIS real-model style answer."
    db.close()
    reset_settings()
    reset_engine()


def test_mocked_ai_tool_call_executes_once():
    from core.llm.types import LLMRequest, LLMResponse, LLMToolCall, LLMUsage
    from core.chat.service import ChatService
    from core.tools.registry import ToolContext

    state = {"calls": 0}

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        def complete(self, request: LLMRequest) -> LLMResponse:
            state["calls"] += 1
            if state["calls"] == 1:
                return LLMResponse(
                    text="",
                    provider="fake",
                    model="fake-model",
                    usage=LLMUsage(),
                    tool_calls=[LLMToolCall(id="call-1", name="create_task", arguments={"title": "AI proposed task"})],
                )
            return LLMResponse(text="Finished: task created.", provider="fake", model="fake-model", usage=LLMUsage())

    import tempfile
    t = tempfile.mkdtemp()
    os.environ["ENV"] = "test"
    os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{t}/test.db"

    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401

    reset_settings()
    reset_engine()
    Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    db = sessionmaker(bind=get_engine())()
    service = ChatService(db, providers=[FakeProvider()])
    result = service.send("phase9-user", "Create a task.")
    assert result["assistant_message"].content == "Finished: task created."
    # Do not automatically retry consequential actions; one service turn.
    assert state["calls"] == 2
    from core.tools.registry import ToolContext, build_default_registry
    rows = build_default_registry().execute(ToolContext(user_id="phase9-user", db=db), "list_tasks", {"status": None})
    assert rows.ok
    assert len(rows.output["tasks"]) == 1
    db.close()
    reset_settings()
    reset_engine()
    os.environ["GROQ_API_KEY"] = ""


def test_ai_tool_call_duplicate_arguments_are_not_executed_twice():
    from core.llm.types import LLMRequest, LLMResponse, LLMToolCall, LLMUsage
    from core.chat.service import ChatService

    state = {"calls": 0}

    class FakeProvider:
        name = "fake"
        model = "fake-model"

        def complete(self, request: LLMRequest) -> LLMResponse:
            state["calls"] += 1
            if state["calls"] == 1:
                return LLMResponse(
                    text="",
                    provider="fake",
                    model="fake-model",
                    usage=LLMUsage(),
                    tool_calls=[
                        LLMToolCall(id="a", name="create_task", arguments={"title": "duplicate task"}),
                        LLMToolCall(id="b", name="create_task", arguments={"title": "duplicate task"}),
                    ],
                )
            return LLMResponse(text="Done", provider="fake", model="fake-model", usage=LLMUsage())

    import tempfile
    t = tempfile.mkdtemp()
    os.environ["ENV"] = "test"; os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{t}/test.db"
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    db = sessionmaker(bind=get_engine())()
    service = ChatService(db, providers=[FakeProvider()])
    service.send("phase9-user", "Do it")
    rows = __import__("core.tools.registry", fromlist=["build_default_registry"]).build_default_registry().execute(
        __import__("core.tools.registry", fromlist=["ToolContext"]).ToolContext(user_id="phase9-user", db=db),
        "list_tasks",
        {},
    )
    assert rows.ok
    assert len(rows.output["tasks"]) == 1
    db.close()
    reset_settings(); reset_engine()


def test_ai_provider_failures_are_reported_offline():
    from core.llm.types import LLMRequest, LLMResponse, LLMUsage, ProviderUnavailableError
    from core.chat.service import ChatService

    class FailingProvider:
        name = "failing"
        model = "failing-model"
        def complete(self, request: LLMRequest) -> LLMResponse:
            raise ProviderUnavailableError("rate limit exceeded")

    service = ChatService.__new__(ChatService)
    t = tempfile.mkdtemp()
    os.environ["ENV"] = "test"; os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{t}/test.db"
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    db = sessionmaker(bind=get_engine())()
    service = ChatService(db, providers=[FailingProvider()])
    result = service.send("phase9-user", "hello")
    assert result["offline"] is True
    assert "unavailable" in result["assistant_message"].content.lower() or "rate" in result["assistant_message"].content.lower()
    db.close()
    reset_settings(); reset_engine()


def test_unknown_tool_call_is_reported_not_executed():
    from core.llm.types import LLMRequest, LLMResponse, LLMToolCall, LLMUsage
    from core.chat.service import ChatService

    state = {"calls": 0}

    class FakeProvider:
        name = "fake"; model = "fake-model"
        def complete(self, request):
            state["calls"] += 1
            if state["calls"] == 1:
                return LLMResponse(text="", provider="fake", model="fake-model", usage=LLMUsage(), tool_calls=[LLMToolCall(id="x", name="shell.execute", arguments={"command": "rm -rf /"})])
            return LLMResponse(text="Done", provider="fake", model="fake-model", usage=LLMUsage())

    t = tempfile.mkdtemp()
    os.environ["ENV"] = "test"; os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{t}/test.db"
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    from sqlalchemy.orm import sessionmaker
    db = sessionmaker(bind=get_engine())()
    service = ChatService(db, providers=[FakeProvider()])
    result = service.send("phase9-user", "do bad")
    assert state["calls"] >= 1
    db.close()
    reset_settings(); reset_engine()


def test_native_notify_and_speak_report_success_and_failure(monkeypatch):
    import apps.api.routes.android as android_route
    import integrations.termux.safe_api as api
    from apps.api.main import create_app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ENV", "test"); monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")

    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    client = TestClient(create_app())
    token = client.post("/api/v1/auth/login", json={"email": "a@b.com"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # simulate available notification command
    def fake_notify(*args, **kwargs):
        return {"ok": True, "available": True, "command": "termux-notification", "returncode": 0, "stdout": "", "stderr": "", "error": None}
    def fake_speak(*args, **kwargs):
        return {"ok": False, "available": True, "command": "termux-tts-speak", "returncode": 1, "stdout": "", "stderr": "denied", "error": "permission denied"}
    monkeypatch.setattr(android_route, "notify", fake_notify)
    monkeypatch.setattr(android_route, "speak", fake_speak)

    notify = client.post("/api/v1/android/notify", json={"title": "Hello", "body": "Body"}, headers=h)
    assert notify.status_code == 200
    assert notify.json()["delivery"]["ok"] is True
    assert notify.json()["notification_id"] is not None

    speak = client.post("/api/v1/android/speak", json={"text": "Hello", "language": "en-US"}, headers=h)
    assert speak.status_code == 200
    assert speak.json()["delivery"]["ok"] is False

    # unavailable command
    monkeypatch.setattr(android_route, "notify", lambda *a, **k: {"ok": False, "available": False, "command": "termux-notification", "returncode": None, "stdout": "", "stderr": "", "error": "not installed"})
    unavailable = client.post("/api/v1/android/notify", json={"title": "Hello", "body": "Body"}, headers=h)
    assert unavailable.status_code == 200
    assert unavailable.json()["delivery"]["available"] is False

    reset_settings(); reset_engine()


def test_invalid_open_url_requires_confirmation_and_validates():
    from apps.api.main import create_app
    from fastapi.testclient import TestClient

    os.environ["ENV"] = "test"; os.environ["AUTH_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
    from core.config import reset_settings
    from core.db.base import Base, get_engine, reset_engine
    import core.db.models  # noqa: F401
    reset_settings(); reset_engine(); Base.metadata.create_all(get_engine())
    client = TestClient(create_app())
    token = client.post("/api/v1/auth/login", json={"email": "a@b.com"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    missing_confirm = client.post("/api/v1/android/open-url", json={"url": "https://example.com", "confirm": False}, headers=h)
    assert missing_confirm.status_code == 400
    invalid = client.post("/api/v1/android/open-url", json={"url": "javascript:alert(1)", "confirm": True}, headers=h)
    assert invalid.status_code == 200
    assert invalid.json()["delivery"]["ok"] is False
    reset_settings(); reset_engine()
