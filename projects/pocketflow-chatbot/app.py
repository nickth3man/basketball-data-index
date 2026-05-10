import os
from pathlib import Path
from typing import Any

import gradio as gr
from dotenv import load_dotenv

from flow import chat_flow
from utils.get_full_schema import get_full_schema

load_dotenv()

DEFAULT_DB_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "test-db" / "nba.duckdb"
)


def build_shared() -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable is required")

    model = os.environ.get("OPENROUTER_MODEL")
    if not model:
        raise RuntimeError("OPENROUTER_MODEL environment variable is required")

    db_path = os.environ.get("DUCKDB_PATH", DEFAULT_DB_PATH)
    db_query_timeout = int(os.environ.get("DB_QUERY_TIMEOUT", "30"))

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


shared = build_shared()


def respond(message: str, history: list[list[str | None]]) -> str:
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
    shared.clear()
    shared.update(build_shared())


with gr.Blocks(
    title="NBA Basketball Chatbot",
    theme=gr.themes.Soft(),  # pyright: ignore[reportPrivateImportUsage]
) as demo:
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

    def handle_submit(
        message: str, history: list[list[str | None]]
    ) -> tuple[str, list[list[str | None]]]:
        response = respond(message, history)
        history.append([message, response])
        return "", history

    msg.submit(handle_submit, [msg, chatbot], [msg, chatbot])

    clear.click(reset_conversation, outputs=[], queue=False)


if __name__ == "__main__":
    demo.launch()
