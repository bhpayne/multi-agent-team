#!/usr/bin/env python3

from typing import Any, Dict, List
import re
import subprocess
from configure_llm import Config


class Bash:
    """
    An implementation of a tool that executes Bash commands
    """

    def __init__(self, config: Config):
        self.cwd = config.root_dir  # The current working directory
        self._allowed_commands = config.allowed_commands  # Allowed commands

    def _extract_commands(self, cmd: str) -> List[str]:
        """
        Splits command chain by pipes and semicolons, extracting the base executable
        of each segment to cross-reference with the allowlist.
        """
        extracted = []
        # Split sequential commands (;)
        for part in cmd.split(";"):
            # Split piped commands (|)
            for piped in part.split("|"):
                cleaned = piped.strip()
                if cleaned:
                    # Capture the first word (the command binary itself)
                    extracted.append(cleaned.split()[0])
        return extracted

    def exec_bash_command(self, cmd: str) -> Dict[str, str]:
        """
        Execute the bash command after getting confirmation from the user.
        If the command contains line breaks, it is split and executed line-by-line.
        """
        if not cmd:
            return {"error": "No command was provided"}

        # Identify line breaks, split into separate lines, and filter out empty lines
        lines = [line.strip() for line in cmd.splitlines() if line.strip()]
        if not lines:
            return {"error": "No command was provided"}

        stdout_parts = []
        stderr_parts = []
        last_cwd = self.cwd

        for line in lines:
            # Check the allowlist for each individual line
            allowed = True
            for cmd_part in self._extract_commands(line):
                if cmd_part not in self._allowed_commands:
                    allowed = False
                    break

            if not allowed:
                return {
                    "error": f"Parts of this command were not in the allowlist: '{line}'"
                }

            # Run the single line command
            res = self._run_bash_command(line)

            # Accumulate stdout and stderr
            if (
                res.get("stdout")
                and res["stdout"]
                != "Command executed successfully, without any output."
            ):
                stdout_parts.append(res["stdout"])
            if res.get("stderr"):
                stderr_parts.append(res["stderr"])

            # Propagate working directory changes to subsequent lines
            last_cwd = res.get("cwd", last_cwd)
            self.cwd = last_cwd

        # Aggregate the collected output of all lines
        final_stdout = (
            "\n".join(stdout_parts)
            if stdout_parts
            else "Command executed successfully, without any output."
        )
        final_stderr = "\n".join(stderr_parts) if stderr_parts else ""

        return {"stdout": final_stdout, "stderr": final_stderr, "cwd": last_cwd}

    def to_json_schema(self) -> Dict[str, Any]:
        """
        Convert the function signature to a JSON schema for LLM tool calling.
        """
        return {
            "type": "function",
            "function": {
                "name": "exec_bash_command",
                "description": "Execute a bash command and return stdout/stderr and the working directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {
                            "type": "string",
                            "description": "The bash command to execute",
                        }
                    },
                    "required": ["cmd"],
                },
            },
        }

    def _run_bash_command(self, cmd: str) -> Dict[str, str]:
        """
        Runs the bash command and catches exceptions (if any).
        """
        stdout = ""
        stderr = ""
        new_cwd = self.cwd

        try:
            # Wrap the command so we can keep track of the working directory.
            wrapped = f"{cmd};echo __END__;pwd"
            result = subprocess.run(
                wrapped,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                executable="/bin/bash",
            )
            stderr = result.stderr
            # Find the separator marker
            split = result.stdout.split("__END__")
            stdout = split[0].strip()

            # If no output/error at all, inform that the call was successful.
            if not stdout and not stderr:
                stdout = "Command executed successfully, without any output."

            # Get the new working directory, and change it
            new_cwd = split[-1].strip()
            self.cwd = new_cwd
        except Exception as e:
            stdout = ""
            stderr = str(e)

        return {"stdout": stdout, "stderr": stderr, "cwd": new_cwd}


# EOF
