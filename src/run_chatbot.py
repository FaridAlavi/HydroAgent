import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure src and root directories are in sys.path
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from pump_inlet_scheduling import DEFAULT_INPUT_DIR

DEFAULT_KNOWLEDGE_BASE_DIR = _root_dir / "knowledge_base"


def _load_knowledge_base(knowledge_base_dir):
    knowledge_base_dir = Path(knowledge_base_dir)
    if not knowledge_base_dir.exists():
        return "No local knowledge-base files were found."

    sections = []
    for path in sorted(knowledge_base_dir.rglob("*.md")):
        relative_path = path.relative_to(knowledge_base_dir)
        sections.append(
            f"## {relative_path}\n\n{path.read_text(encoding='utf-8').strip()}"
        )
    return "\n\n".join(sections)


def _build_instructions(input_dir, knowledge_base_dir):
    knowledge_base = _load_knowledge_base(knowledge_base_dir)
    return f"""
You help users inspect, explain, update, solve, and visualize a pump and inlet
scheduling model. The active scenario folder is {Path(input_dir)}. All model
operations are available through the connected MCP server. Use its tools rather
than claiming that an operation was performed.

Use the local knowledge base below to explain model elements and ask for missing
details. For the current topology, call create_topology_explanation. To solve or
calculate a schedule, call run_optimization. To inspect or plot results, call
the appropriate read or plot tool. After creating a plot, call open_plot_file.

Indexes are zero-based. If the user says "pump number 1", interpret it as index
1 unless they explicitly say "first pump", and state that interpretation before
writing. Ask a short clarification question when a pump/inlet index, mode, time,
or required model field is missing or ambiguous.

Before calling create_pumps_json, create_inlets_json, create_storage_json,
create_topology_json, or create_user_constraints, gather all required values,
summarize the exact proposed update, and ask for confirmation. Do not call a
write tool until the user confirms. Running the optimizer and reading or plotting
data do not require confirmation.

When adding a pump, inlet, inflow, storage, or level, update every affected JSON
file consistently. Pumps and inlets generally require matching topology elements,
connections, and storage-balance entries. For a pump that must be off whenever
an upstream storage level is above a downstream level, use the supported
head_based_pump_mode_constraint topology equation after confirming the pump index
and required mode.

After a tool succeeds, report the file it updated or created. After writing user
constraints, summarize them and ask whether the user wants to run the optimizer.

Local knowledge base:

{knowledge_base}
""".strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Chat with an OpenAI agent that consumes pump scheduling tools over MCP."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--knowledge-base-dir", type=Path, default=DEFAULT_KNOWLEDGE_BASE_DIR
    )
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5"))
    return parser.parse_args()


async def run_chatbot(args):
    try:
        from agents import Agent, Runner
        from agents.mcp import MCPServerStdio
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The OpenAI Agents SDK is not installed. Run: pip install -r requirements.txt"
        ) from exc

    server_script = Path(__file__).with_name("mcp_server.py").resolve()
    server_params = {
        "command": sys.executable,
        "args": [
            str(server_script),
            "--input-dir",
            str(args.input_dir.resolve()),
        ],
        "cwd": str(_root_dir.resolve()),
    }

    async with MCPServerStdio(
        params=server_params,
        cache_tools_list=True,
        name="Pump Scheduling MCP Server",
        client_session_timeout_seconds=30,
    ) as mcp_server:
        agent = Agent(
            name="Pump Scheduling Assistant",
            model=args.model,
            instructions=_build_instructions(args.input_dir, args.knowledge_base_dir),
            mcp_servers=[mcp_server],
        )
        conversation = []

        print("Pump scheduling MCP chatbot")
        print("Ask about the model, request input changes, add constraints, or run the optimizer.")
        print("Type 'exit' or 'quit' to stop.")
        print(f"Input folder: {args.input_dir}")
        print(f"Knowledge base: {args.knowledge_base_dir}")
        print()

        while True:
            try:
                user_input = input("User: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break

            conversation.append({"role": "user", "content": user_input})
            print("\nAssistant: ", end="", flush=True)

            try:
                result = await Runner.run(agent, conversation)
                assistant_message = result.final_output
                print(assistant_message)
                print()
                conversation = result.to_input_list()
            except Exception as exc:
                print(f"\nError: {exc}\n")


def main():
    asyncio.run(run_chatbot(parse_args()))


if __name__ == "__main__":
    main()
