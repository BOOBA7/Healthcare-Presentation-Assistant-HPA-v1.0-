import pytest

from app.application.services.observability import observe_llm_call, snapshot


def test_observe_llm_call_records_success_without_prompt_content():
    assert observe_llm_call("test_stage", "private prompt text", lambda: "ok") == "ok"
    assert snapshot()["llm_call"] >= 1


def test_observe_llm_call_records_errors_and_reraises():
    with pytest.raises(RuntimeError):
        observe_llm_call("test_stage", "private prompt text", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert snapshot()["llm_call"] >= 2
