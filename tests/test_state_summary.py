from app.ai.prompt_builders.state_summary_builder import StateSummaryBuilder
from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.tools import COGNITIVE_TOOLS


def test_state_summary_describes_the_initial_workflow_state():
    summary = StateSummaryBuilder().build(GraphState())

    assert "Context complete: no" in summary
    assert "Presentation created: no" in summary
    assert "Validated resources: 0" in summary
    assert "Blueprint generated: no" in summary


def test_human_validation_is_not_an_agent_tool():
    tool_names = {tool.name for tool in COGNITIVE_TOOLS}

    assert "validate_resources" not in tool_names
    assert "validate_blueprint" not in tool_names
    assert "validate_slides" not in tool_names
    assert "validate_final_presentation" not in tool_names
    assert "record_presentation_details" in tool_names
