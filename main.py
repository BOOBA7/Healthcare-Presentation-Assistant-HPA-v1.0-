import uuid

from langchain_core.messages import HumanMessage

from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
from app.ai.workflows.graph_state import GraphState
from app.core.logging import configure_logging


def _extract_text(message) -> str:
    if hasattr(message, "text") and message.text:
        return message.text

    content = getattr(message, "content", None)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()

    return str(message)


def main() -> None:
    configure_logging()
    print("=" * 70)
    print("Healthcare Presentation Assistant (HPA)")
    print("=" * 70)
    print("Type 'exit' to quit.\n")

    thread_id = str(uuid.uuid4())
    print(f"Thread ID : {thread_id}\n")

    agent = HealthcarePresentationAgent()
    state = GraphState()

    while True:
        user_input = input("You > ").strip()

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            break

        state.messages.append(HumanMessage(content=user_input))

        try:
            result = agent.invoke(
                state,
                thread_id=thread_id,
            )
        except Exception as exc:
            message = str(exc)
            print()
            print("Assistant >")
            if "RESOURCE_EXHAUSTED" in message or "429" in message:
                print(
                    "Le quota Gemini est atteint. Attendez le délai indiqué par Gemini "
                    "ou utilisez une clé/API avec un quota disponible."
                )
            else:
                print(f"Impossible de contacter le modèle : {message}")
            print()
            continue

        state = GraphState(**result)

        messages = result.get("messages", [])
        if not messages:
            print("\nAssistant >")
            print("(no message returned)\n")
            continue

        last_message = messages[-1]

        print()
        print("Assistant >")
        print(_extract_text(last_message))
        print()


if __name__ == "__main__":
    main()
