#!/usr/bin/env python3

import json
import argparse

from configure_llm import Config
from run_bash import Bash
from helpers import Messages, LLM


def confirm_execution(cmd: str) -> bool:
    """Ask the user whether the suggested command should be executed."""
    return input(f"   Execute '{cmd}'? [y/N]: ").strip().lower() == "y"


def main(config: Config, proceed_without_waiting: bool):
    bash = Bash(config)
    # The model
    llm = LLM(config)
    # The conversation history, with the system prompt
    messages = Messages(config.system_prompt)
    print("[INFO] Type 'quit' at any time to exit the agent loop.\n")

    # The main agent loop
    while True:
        # Get user message.
        user = input(f"['{bash.cwd}' 🙂] ").strip()

        if user.lower() == "quit":
            print("\n[🤖] Shutting down. Bye!\n")
            break

        if user.lower().lstrip().startswith("bash:"):
            command = user.removeprefix("bash:")
            tool_call_result = bash.exec_bash_command(command)
            print(tool_call_result)
            continue  # skips the rest of the code and immediately starts the next loop

        if (
            not user
        ):  # an empty string evaluates to False in a boolean context. Therefore, `not user` becomes True when the string is empty.
            continue  # skips the rest of the code and immediately starts the next loop
        # Always tell the agent where the current working directory is to avoid confusions.
        user += f"\n Current working directory: `{bash.cwd}`"
        messages.add_user_message(user)

        # The tool-call/response loop
        while True:
            print("\n[🤖] Calling LLM...")
            response, tool_calls = llm.query(messages, [bash.to_json_schema()])

            # Store the assistant response containing tool calls to keep history valid
            if response or tool_calls:
                clean_response = ""
                if response:
                    clean_response = response.strip()
                    # Do not store the thinking part to save context space
                    if "</think>" in clean_response:
                        clean_response = clean_response.split("</think>")[-1].strip()

                messages.add_assistant_message(clean_response, tool_calls)

            # Process tool calls
            if tool_calls:
                for tc in tool_calls:
                    function_name = tc.function.name
                    function_args = json.loads(tc.function.arguments)

                    # Ensure it's calling the right tool
                    if (
                        function_name != "exec_bash_command"
                        or "cmd" not in function_args
                    ):
                        tool_call_result = json.dumps(
                            {"error": "Incorrect tool or function argument"}
                        )
                    else:
                        command = function_args["cmd"]
                        # Confirm execution with the user
                        if confirm_execution(command) or proceed_without_waiting:
                            tool_call_result = bash.exec_bash_command(command)
                        else:
                            tool_call_result = {
                                "error": "The user declined the execution of this command."
                            }

                    # Add the tool result back to history, providing id and name
                    messages.add_tool_message(tool_call_result, tc.id, function_name)
            else:
                # Display the assistant's message to the user.
                if response:
                    clean_response = response.strip()
                    if "</think>" in clean_response:
                        clean_response = clean_response.split("</think>")[-1].strip()
                    if clean_response:
                        print(clean_response)
                        print("-" * 80 + "\n")
                break


if __name__ == "__main__":

    theparser = argparse.ArgumentParser(description="agentic LLM")

    # True if flag is present, False if absent
    theparser.add_argument(
        "--log", action="store_true", help="log prompts and responses to file"
    )

    # True if flag is present, False if absent
    theparser.add_argument(
        "--isolated",
        action="store_true",
        help="agent is inside a container or virtual machine, so additional commands to change and remove files are available",
    )

    # if nothing is specified then defaults to None
    theparser.add_argument("--dir", type=str, help="starting directory")

    # True if flag is present, False if absent
    theparser.add_argument(
        "--proceed", action="store_true", help="don't prompt the user for each command"
    )

    args = theparser.parse_args()

    proceed_without_waiting = args.proceed

    # Pass the command line flag directly into the Config initialization
    config = Config(
        log_prompts=args.log,
        inside_container_or_virtual_machine=args.isolated,
        starting_directory=args.dir,
    )
    main(config, proceed_without_waiting)

# EOF
