#!/usr/bin/env python3

import json
import os
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

from configure_llm import Config


class Messages:
    """
    An abstraction for a list of system/user/assistant/tool messages.

    This is the context history for iterative interactions in the same session
    """

    def __init__(self, system_message: str = ""):
        self.system_message = None
        self.messages = []
        self.set_system_message(system_message)

    def set_system_message(self, message):
        self.system_message = {"role": "system", "content": message}

    def add_user_message(self, message):
        self.messages.append({"role": "user", "content": message})

    def add_assistant_message(self, message, tool_calls=None):
        payload = {"role": "assistant", "content": message or ""}
        if tool_calls:
            # Reconstruct the tool_calls list to match OpenAI specification
            payload["tool_calls"] = []
            for tc in tool_calls:
                tc_data = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                # Preserve extra_content (containing thought_signature) for Gemini compatibility
                if getattr(tc, "extra_content", None) is not None:
                    tc_data["extra_content"] = tc.extra_content
                payload["tool_calls"].append(tc_data)
        self.messages.append(payload)

    def add_tool_message(self, message, id, name):
        # Convert output dicts (like stdout/stderr results) into standard JSON strings
        if isinstance(message, dict):
            content_str = json.dumps(message)
        else:
            content_str = str(message)

        # Gemini strictly requires the "name" field to match the original function name
        self.messages.append(
            {"role": "tool", "content": content_str, "tool_call_id": id, "name": name}
        )

    def to_list(self) -> List[Dict[str, str]]:
        """
        Convert to a list of messages.
        """
        return [self.system_message] + self.messages


# Simple classes to mimic the OpenAI tool call objects
class ToolCallFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class ToolCall:
    def __init__(
        self,
        id: str,
        function: ToolCallFunction,
        type: str = "function",
        extra_content: Any = None,
    ):
        self.id = id
        self.function = function
        self.type = type
        self.extra_content = extra_content


class LLM:
    """
    An abstraction to prompt an LLM using Python's standard library.
    """

    def __init__(self, config: Config):
        self.config = config
        self.sequence_number = 1

        self.logs_dir = os.path.join(self.config.root_dir, "logs")
        # Only create the 'logs' directory if logging is explicitly requested
        if self.config.log_prompts:
            os.makedirs(self.logs_dir, exist_ok=True)

        print(f"Using model '{config.llm_model_name}' from '{config.llm_base_url}'")

    def query(
        self,
        messages: Messages,
        tools: List[Dict[str, Any]],
        max_tokens=None,
    ) -> Tuple[str, List[ToolCall]]:
        base_url = self.config.llm_base_url.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            url = f"{base_url}/chat/completions"
        else:
            url = base_url

        payload = {
            "model": self.config.llm_model_name,
            "messages": messages.to_list(),
            "temperature": self.config.llm_temperature,
            "top_p": self.config.llm_top_p,
        }

        if tools:
            payload["tools"] = tools
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Variables used for generating log filenames
        model_name = self.config.llm_model_name
        seq_str = f"{self.sequence_number:06d}"

        # --- Capture and log the prompt payload ---
        if self.config.log_prompts:
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d_%H-%M-%S.%f")[:-4]
            prompt_filename = f"{timestamp}_{model_name}_{seq_str}_prompt.log"
            prompt_filepath = os.path.join(self.logs_dir, prompt_filename)

            try:
                with open(prompt_filepath, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"\n[Warning] Failed to write prompt log: {e}")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.llm_api_key}",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        res_json = {}
        error_occurred = False
        error_message = ""

        try:
            with urllib.request.urlopen(req) as response:
                res_data = response.read().decode("utf-8")
                res_json = json.loads(res_data)
        except urllib.error.HTTPError as e:
            error_occurred = True
            error_content = e.read().decode("utf-8")
            print(f"\n[Error] API Request failed (HTTP {e.code}):")
            try:
                res_json = json.loads(error_content)
                print(json.dumps(res_json, indent=2))
            except Exception:
                res_json = {"error": error_content}
                print(error_content)
            error_message = f"Error: API call failed with status code {e.code}"
        except Exception as e:
            error_occurred = True
            print(f"\n[Error] Connection failed: {e}")
            res_json = {"error": str(e)}
            error_message = "Error: Failed to connect to the model provider."

        # --- Capture and log the response payload ---
        if self.config.log_prompts:
            resp_now = datetime.now()
            resp_timestamp = resp_now.strftime("%Y-%m-%d_%H-%M-%S.%f")[:-4]
            response_filename = f"{resp_timestamp}_{model_name}_{seq_str}_response.log"
            response_filepath = os.path.join(self.logs_dir, response_filename)

            try:
                with open(response_filepath, "w", encoding="utf-8") as file_handle:
                    json.dump(res_json, file_handle, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"\n[Warning] Failed to write response log: {e}")

        # Increment sequence counter for subsequent queries
        self.sequence_number += 1

        if error_occurred:
            return error_message, []

        choices = res_json.get("choices", [])
        if not choices:
            return "", []

        message_data = choices[0].get("message", {})
        content = message_data.get("content") or ""

        raw_tool_calls = message_data.get("tool_calls") or []

        # Fallback parser for local models (like Gemma via llama_cpp.server)
        # that emit native tool calls in `content` instead of structured `tool_calls`.
        if not raw_tool_calls and "<|tool_call>" in content:
            import re
            # Match pattern: <|tool_call>call:name{args}<tool_call|>
            pattern = r"<\|tool_call>call:([a-zA-Z0-9_]+)\s*(\{.*?\})<tool_call\|>"
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                print(matches)
                raw_tool_calls = []
                for func_name, args_str in matches:
                    # Clean up Gemma's special string delimiters <|"|> to standard double quotes
                    json_candidate = args_str.replace('<|"|>', '"')
                    # Ensure unquoted keys are properly quoted for JSON parsing (e.g., cmd: -> "cmd":)
                    json_candidate = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_candidate)
                    
                    try:
                        json.loads(json_candidate)
                        args_final = json_candidate
                    except Exception:
                        args_final = json.dumps({"cmd": args_str})

                    raw_tool_calls.append({
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": args_final
                        }
                    })
                # Remove the raw tool-call tags from the text content
                content = re.sub(pattern, "", content).strip()
                print(content)
        
        tool_calls = []
        for tc_dict in raw_tool_calls:
            func_dict = tc_dict.get("function", {})
            func_obj = ToolCallFunction(
                name=func_dict.get("name", ""),
                arguments=func_dict.get("arguments", "{}"),
            )

            tc_id = tc_dict.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            extra_content = tc_dict.get("extra_content")  # Extract signature metadata

            tool_calls.append(
                ToolCall(
                    id=tc_id,
                    function=func_obj,
                    type=tc_dict.get("type", "function"),
                    extra_content=extra_content,  # Pass signature metadata
                )
            )

        return content, tool_calls


# EOF
