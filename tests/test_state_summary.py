from app.ai.prompt_builders.state_summary_builder import StateSummaryBuilder
from app.ai.workflows.graph_state import GraphState


def test_state_summary_describes_the_initial_workflow_state():
    summary = StateSummaryBuilder().build(GraphState())

    assert "Context complete: no" in summary
    assert "Presentation created: no" in summary
    assert "Validated resources: 0" in summary
    assert "Blueprint generated: no" in summary
