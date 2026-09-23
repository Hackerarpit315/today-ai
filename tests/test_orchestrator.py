from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.orchestrator.pipeline import Orchestrator, run_pipeline
from app.orchestrator.schemas import PipelineRequest
from app.schemas.context import ContextItem
from app.schemas.research import ResearchSource

REQUEST_ID = UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def source(source_id="s1", content="The application deadline is 30 September 2026."):
    return ResearchSource(
        source_id=source_id,
        title="Application facts",
        url="https://example.com/facts",
        content=content,
        source_type="official",
    )


def context_item():
    return ContextItem(
        context_id="c1",
        content="application portal documents",
        context_type="project",
        tags=["application"],
    )


def request(text="Prepare my application"):
    return PipelineRequest(
        request_id=REQUEST_ID,
        text=text,
        current_datetime=NOW,
        available_context=[context_item()],
        research_sources=[source()],
    )


def test_successful_end_to_end_pipeline():
    result = Orchestrator().run(request())
    assert result.status == "success"
    assert result.current_stage == "today"
    assert result.errors == []
    assert all(stage in result.stage_results for stage in ("input", "intent", "context", "research", "verification", "planning", "priority", "today"))


def test_request_id_propagates_to_all_stage_outputs():
    result = Orchestrator().run(request())
    for stage in result.stage_results.values():
        if isinstance(stage, dict) and "request_id" in stage:
            assert stage["request_id"] == str(REQUEST_ID)


def test_input_stage_preserves_normalized_content():
    result = Orchestrator().run(request("  Prepare my application  "))
    assert result.stage_results["input"]["content"] == "Prepare my application"


def test_deterministic_output_for_same_inputs():
    first = Orchestrator().run(request()).model_dump(mode="json")
    second = Orchestrator().run(request()).model_dump(mode="json")
    assert first == second


def test_explicit_datetime_is_used_by_today():
    result = Orchestrator().run(request())
    assert result.today["current_datetime"] == NOW.isoformat().replace("+00:00", "Z")


def test_datetime_timezone_is_required():
    with pytest.raises(ValidationError):
        PipelineRequest(request_id=REQUEST_ID, text="hello", current_datetime=datetime(2026, 9, 23, 12))


def test_stage_order_is_m1_to_m8():
    result = Orchestrator().run(request())
    assert list(result.stage_results) == ["input", "intent", "context", "research", "verification", "planning", "priority", "today"]


def test_stage_result_preservation():
    result = Orchestrator().run(request())
    assert result.stage_results["intent"] == result.intent
    assert result.stage_results["context"] == result.context
    assert result.stage_results["research"] == result.research
    assert result.stage_results["verification"] == result.verification
    assert result.stage_results["planning"] == result.planning
    assert result.stage_results["priority"] == result.priority
    assert result.stage_results["today"] == result.today


def test_empty_input_fails_at_input():
    result = Orchestrator().run(request("   "))
    assert result.status == "failed"
    assert result.current_stage == "input"
    assert result.errors[0].code == "validation_error" or result.errors[0].code == "validation_error"


def test_invalid_input_type_cannot_enter_pipeline():
    with pytest.raises(ValidationError):
        PipelineRequest(request_id=REQUEST_ID, text="hello", current_datetime=NOW, input_type="voice")


def test_context_is_forwarded_to_context_engine():
    result = Orchestrator().run(request())
    assert result.context["context_used"] is True
    assert result.context["relevant_context"][0]["context_id"] == "c1"


def test_empty_context_is_supported():
    req = request()
    req = req.model_copy(update={"available_context": []})
    result = Orchestrator().run(req)
    assert result.status == "success"
    assert result.context["context_used"] is False


def test_research_uses_only_supplied_sources():
    result = Orchestrator().run(request())
    assert result.research["sources_found"] == 1
    assert result.research["results"][0]["source_id"] == "s1"


def test_empty_research_sources_are_supported_without_network():
    req = request().model_copy(update={"research_sources": []})
    result = Orchestrator().run(req)
    assert result.status == "success"
    assert result.research["sources_found"] == 0
    assert result.verification["verification_status"] == "unverified"


def test_verification_receives_research_content_from_supplied_source():
    result = Orchestrator().run(request())
    assert result.verification["request_id"] == str(REQUEST_ID)
    assert result.verification["insufficient_claims"] or result.verification["verified_claims"]


def test_planning_receives_verified_information_contract():
    result = Orchestrator().run(request())
    assert result.planning["request_id"] == str(REQUEST_ID)
    assert result.planning["total_steps"] > 0


def test_priority_receives_planning_steps():
    result = Orchestrator().run(request())
    assert result.priority["plan_id"] == result.planning["plan_id"]
    assert result.priority["total_steps"] == result.planning["total_steps"]


def test_today_receives_priority_output():
    result = Orchestrator().run(request())
    assert result.today["plan_id"] == result.priority["plan_id"]
    assert result.today["request_id"] == str(REQUEST_ID)


def test_pipeline_does_not_execute_actions():
    result = Orchestrator().run(request())
    assert "action" not in result.stage_results
    assert "execution" not in result.stage_results


def test_pipeline_does_not_include_modules_9_to_15():
    result = Orchestrator().run(request())
    assert list(result.stage_results) == ["input", "intent", "context", "research", "verification", "planning", "priority", "today"]


def test_failure_at_intent_stops_later_stages():
    calls = []
    class Intent:
        def process_intent(self, payload):
            calls.append("intent")
            raise RuntimeError("internal details")
    fake = {"intent": Intent()}
    result = Orchestrator(fake).run(request())
    assert result.status == "failed"
    assert result.current_stage == "intent"
    assert calls == ["intent"]
    assert set(result.stage_results) == {"input"}
    assert "internal details" not in result.errors[0].message


def test_failure_at_context_stops_research_and_later_stages():
    calls = []
    class Context:
        def process_context(self, payload):
            calls.append("context")
            raise RuntimeError("secret stack detail")
    class Research:
        def process_research(self, payload):
            calls.append("research")
            raise AssertionError("must not run")
    result = Orchestrator({"context": Context(), "research": Research()}).run(request())
    assert result.current_stage == "context"
    assert calls == ["context"]
    assert set(result.stage_results) == {"input", "intent"}
    assert "secret stack detail" not in result.errors[0].message


def test_failure_at_research_stops_verification_and_later_stages():
    calls = []
    class Research:
        def process_research(self, payload):
            calls.append("research")
            raise RuntimeError("network must never be called")
    class Verification:
        def verify_research(self, payload):
            calls.append("verification")
            raise AssertionError("must not run")
    result = Orchestrator({"research": Research(), "verification": Verification()}).run(request())
    assert result.current_stage == "research"
    assert calls == ["research"]
    assert "network" not in result.errors[0].message


def test_failure_at_verification_stops_planning():
    calls = []
    class Verification:
        def verify_research(self, payload):
            calls.append("verification")
            raise RuntimeError("traceback hidden")
    class Planning:
        def create_plan(self, payload):
            calls.append("planning")
            raise AssertionError("must not run")
    result = Orchestrator({"verification": Verification(), "planning": Planning()}).run(request())
    assert result.current_stage == "verification"
    assert calls == ["verification"]
    assert "traceback" not in result.errors[0].message


def test_failure_at_planning_stops_priority():
    calls = []
    class Planning:
        def create_plan(self, payload):
            calls.append("planning")
            raise RuntimeError("planner internals")
    class Priority:
        def prioritize_plan(self, payload):
            calls.append("priority")
            raise AssertionError("must not run")
    result = Orchestrator({"planning": Planning(), "priority": Priority()}).run(request())
    assert result.current_stage == "planning"
    assert calls == ["planning"]


def test_failure_at_priority_stops_today():
    calls = []
    class Priority:
        def prioritize_plan(self, payload):
            calls.append("priority")
            raise RuntimeError("priority internals")
    class Today:
        def build_today(self, payload):
            calls.append("today")
            raise AssertionError("must not run")
    result = Orchestrator({"priority": Priority(), "today": Today()}).run(request())
    assert result.current_stage == "priority"
    assert calls == ["priority"]


def test_failure_at_today_is_reported_safely():
    class Today:
        def build_today(self, payload):
            raise RuntimeError("today internal failure")
    result = Orchestrator({"today": Today()}).run(request())
    assert result.status == "failed"
    assert result.current_stage == "today"
    assert result.errors[0].code == "stage_error"
    assert "internal failure" not in result.errors[0].message


def test_pydantic_stage_validation_error_is_safe():
    class Intent:
        def process_intent(self, payload):
            raise ValidationError.from_exception_data("IntentResponse", [])
    result = Orchestrator({"intent": Intent()}).run(request())
    assert result.status == "failed"
    assert result.current_stage == "intent"
    assert result.errors[0].code == "validation_error"
    assert "ValidationError" not in result.errors[0].message


def test_request_id_is_required_for_deterministic_correlation():
    with pytest.raises(ValidationError):
        PipelineRequest(text="hello", current_datetime=NOW)


def test_research_source_order_is_preserved_for_equal_relevance():
    req = request().model_copy(update={"research_sources": [source("s1"), source("s2")]})
    result = Orchestrator().run(req)
    ids = [item["source_id"] for item in result.research["results"]]
    assert ids == ["s1", "s2"]


def test_different_explicit_datetime_can_change_today_without_machine_clock():
    later = request().model_copy(update={"current_datetime": datetime(2026, 9, 24, 12, tzinfo=timezone.utc)})
    first = Orchestrator().run(request())
    second = Orchestrator().run(later)
    assert first.today["current_datetime"] != second.today["current_datetime"]


def test_run_pipeline_convenience_function():
    result = run_pipeline(
        "Prepare my application",
        request_id=REQUEST_ID,
        current_datetime=NOW,
        available_context=[context_item()],
        research_sources=[source()],
    )
    assert result.status == "success"


def test_stage_errors_are_structured_and_bounded():
    class Input:
        def accept(self, payload):
            raise RuntimeError("hidden implementation stack trace")
    result = Orchestrator({"input": Input()}).run(request())
    assert result.errors[0].stage == "input"
    assert len(result.errors[0].message) <= 500
    assert "Traceback" not in result.errors[0].message


def test_no_external_service_objects_are_required():
    result = Orchestrator().run(PipelineRequest(request_id=REQUEST_ID, text="hello", current_datetime=NOW))
    assert result.status == "success"


def test_pipeline_result_has_all_required_top_level_fields():
    result = Orchestrator().run(request())
    data = result.model_dump()
    for key in ("request_id", "status", "current_stage", "intent", "context", "research", "verification", "planning", "priority", "today", "errors", "stage_results"):
        assert key in data


def test_later_stage_results_are_absent_after_failure():
    class Priority:
        def prioritize_plan(self, payload):
            raise RuntimeError("stop")
    result = Orchestrator({"priority": Priority()}).run(request())
    assert result.today is None
    assert "today" not in result.stage_results


def test_input_validation_error_preserves_request_id():
    result = Orchestrator().run(request(""))
    assert result.request_id == REQUEST_ID


def test_same_explicit_request_id_is_used_even_when_m1_generates_its_own_id():
    result = Orchestrator().run(request())
    assert result.stage_results["input"]["request_id"] == str(REQUEST_ID)
