import os
from pathlib import Path
from typing import Any

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


def main() -> None:
    shared = build_shared()
    print("NBA Basketball Chatbot (CLI)")
    print("Type 'quit' to exit.")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if user_input.lower() in ("quit", "exit", "q"):
            break

        if not user_input:
            continue

        shared["user_message"] = user_input
        shared["chat_history"].append({
            "role": "user",
            "content": user_input,
            "sql": None,
            "error": False,
        })
        chat_flow.run(shared)
        response = shared.get("response", "Sorry, I couldn't generate a response.")
        print(f"Bot: {response}")
        print()


if __name__ == "__main__":
    main()
