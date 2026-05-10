import os
import sys
from pathlib import Path
from typing import Any

import gradio as gr
from dotenv import load_dotenv

from flow import chat_flow
from utils.get_full_schema import get_full_schema

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "test-db" / "nba.duckdb")

_shared: dict[str, Any] | None = None


def build_shared() -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        print(
            "Create a .env file with: OPENROUTER_API_KEY=sk-or-v1-...", file=sys.stderr
        )
        raise SystemExit(1)

    model = os.environ.get("OPENROUTER_MODEL")
    if not model:
        print("ERROR: OPENROUTER_MODEL is not set.", file=sys.stderr)
        print(
            "Create a .env file with: OPENROUTER_MODEL=openai/gpt-4o", file=sys.stderr
        )
        raise SystemExit(1)

    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    db_query_timeout = int(os.environ.get("DB_QUERY_TIMEOUT", "30"))

    if not os.path.isfile(db_path):
        print(f"ERROR: Database not found at: {db_path}", file=sys.stderr)
        print(
            "Set DUCKDB_PATH in .env to point to your nba.duckdb file.", file=sys.stderr
        )
        raise SystemExit(1)

    schema_by_table = get_full_schema(db_path)

    return {
        "db_path": db_path,
        "schema_by_table": schema_by_table,
        "openrouter_api_key": api_key,
        "openrouter_model": model,
        "db_query_timeout": db_query_timeout,
        "max_rows": 200,
        "chat_history": [],
    }


def get_shared() -> dict[str, Any]:
    global _shared
    if _shared is None:
        _shared = build_shared()
    return _shared


def respond(message: str, history: list[dict]) -> str:
    shared = get_shared()
    shared["user_message"] = message
    shared["chat_history"].append({
        "role": "user",
        "content": message,
        "sql": None,
        "error": False,
    })
    chat_flow.run(shared)
    return shared.get("response", "Sorry, I couldn't generate a response.")


def reset_conversation() -> None:
    global _shared
    _shared = None


with gr.Blocks(title="NBA Basketball Chatbot") as demo:
    gr.Markdown(
        "# NBA Basketball Chatbot\n"
        "Ask questions about NBA players, teams, games, and statistics "
        "in plain English."
    )

    chatbot = gr.Chatbot(label="Conversation", height=500)
    msg = gr.Textbox(
        label="Your question",
        placeholder="e.g. Who scored the most points per game in the 2023-24 season?",
    )
    clear = gr.ClearButton([msg, chatbot])

    def handle_submit(message: str, history: list[dict]) -> tuple[str, list[dict]]:
        response = respond(message, history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        return "", history

    msg.submit(handle_submit, [msg, chatbot], [msg, chatbot])

    clear.click(reset_conversation, outputs=[], queue=False)


if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Soft(),  # pyright: ignore[reportPrivateImportUsage]
    )
