#!/usr/bin/env python3

import requests
import json
from git import Repo
from jsonschema import validate as jsonschema_validate
from jsonschema.exceptions import ValidationError as jsonschema_ValidationError
import time


def git_add_commit(filename: str, commit_msg: str) -> str:
    repo.index.add([filename])
    new_commit = repo.index.commit(commit_msg)
    return new_commit.hexsha


def is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:  # Handles JSONDecodeError
        return False


repo = Repo("/opt/git_for_agents")


url = "http://host.docker.internal:8000/v1/chat/completions"

headers = {"Content-Type": "application/json"}


available_commands = [
    "apt",
    "awk",
    "basename",
    "bc",
    "break",
    "cat",
    "cd",
    "chgrp",
    "chmod",
    "chown",
    "continue",
    "cp",
    "curl",
    "date",
    "diff",
    "dmesg",
    "do",
    "du",
    "echo",
    "elif",
    "else",
    "export",
    "fi",
    "find",
    "for",
    "gh",
    "git",
    "glab",
    "grep",
    "head",
    "hostname",
    "if",
    "ifconfig",
    "ls",
    "mkdir",
    "mv",
    "netstat",
    "ping",
    "pip3",
    "podman",
    "pwd",
    "python3",
    "rm",
    "sed",
    "sort",
    "ssh-keygen",
    "ssh",
    "tail",
    "time",
    "touch",
    "tr",
    "wc",
    "wget",
    "xargs",
]


system_prompt_for_commands = """
You are a helpful and concise assistant with the ability to execute commands in the shell.
You engage with users to help answer questions or execute their intent.

When a command is executed, you will be given the output from that command and any errors. 

The bash interpreter's output and current working directory will be given to you every time a
command is executed. 

You are only allowed to execute the following commands. Break complex tasks into shorter commands from this list:

```
{available_commands}
```
"""

system_prompt_for_brainstorming = """
Given the user's request below, brainstorm tasks that would be relevant for decomposing the request.


User's request:
"""


system_prompt_for_decoration_of_tasks = """
A few tasks described below have been identified in a brainstorming session. 
For each task add a set of inputs, assumptions, constraints on starting the task.
Also for each task, specify what the expected output of the task is once completed.
Lastly, for each task, estimate how burdensome this task is. Could this be accomplished simply and quickly or would the task be expected to incur multiple subtasks to complete?

Tasks:
"""


with open(
    "json_schema_for_imp_no_burdensomeness_no_failure_count.json", "r"
) as file_handle:
    json_schema_for_imp_no_burdensomeness_no_failure_count = file_handle.read()

system_prompt_for_create_IMP = """
A few tasks described below have been identified in a brainstorming session. 
Convert the Markdown into the JSON format specified below that captures the sequence of tasks and the dependencies among tasks.
The nodes of the graph are tasks, and the directed edges indicate the order in which to do tasks. 
The predecessor task is the key,
the subsequent task is the value in the edge dictionary.

For each node in the JSON file fill in the "task description", 
"inputs needed for task", "assumptions about the task", 
"constraints on the task", and "expected output from the task".
The "id" value is a distinct string that is used to label the task node and is used in the edge dictionary.

The JSON file must adhere to the schema below. 
```
{json_schema_for_imp_no_burdensomeness_no_failure_count}
```

Tasks:
"""

start_time = time.time()

############################## brainstorming tasks based on user's request ######

elapsed_time = round(time.time() - start_time, 3)
print(f"reading user's request;  {elapsed_time} seconds")

with open("git_for_agents/users_request.md", "r") as file_handle:
    users_request = file_handle.read()

data = {
    "messages": [
        {"role": "user", "content": system_prompt_for_brainstorming + users_request}
    ]
}
brainstorming_response = requests.post(url, headers=headers, json=data)

# print(json.dumps(brainstorming_response.json(), indent=4))

brainstorming_tasks_md = brainstorming_response.json()["choices"][0]["message"][
    "content"
]

with open("git_for_agents/brainstorming_tasks.md", "w") as file_handle:
    file_handle.write(brainstorming_tasks_md)

git_add_commit("brainstorming_tasks.md", "brainstorming tasks")

elapsed_time = round(time.time() - start_time, 3)
print(f"committed brainstorming to git;  {elapsed_time} seconds")

############################## decorate brainstormed tasks with inputs and outputs ############

with open("git_for_agents/brainstorming_tasks.md", "r") as file_handle:
    brainstorming_tasks_md = file_handle.read()

data = {
    "messages": [
        {
            "role": "user",
            "content": system_prompt_for_decoration_of_tasks + brainstorming_tasks_md,
        }
    ]
}
decorated_response = requests.post(url, headers=headers, json=data)

decorated_tasks_md = decorated_response.json()["choices"][0]["message"]["content"]

with open("git_for_agents/decorated_tasks.md", "w") as file_handle:
    file_handle.write(decorated_tasks_md)

git_add_commit("decorated_tasks.md", "brainstorming tasks")

elapsed_time = round(time.time() - start_time, 3)
print(f"committed decorated tasks to git;  {elapsed_time} seconds")


############################## convert decorated tasks into IMP-as-JSON ############

with open("git_for_agents/decorated_tasks.md", "r") as file_handle:
    decorated_tasks_md = file_handle.read()


data = {
    "messages": [
        {
            "role": "user",
            "content": system_prompt_for_create_IMP + decorated_tasks_md,
        }
    ]
}
imp_response = requests.post(url, headers=headers, json=data)


# print(json.dumps(imp_response.json(), indent=4))

imp_as_json = imp_response.json()["choices"][0]["message"]["content"]

with open(
    "git_for_agents/imp_no_burdensomeness_no_failure_count.json", "w"
) as file_handle:
    file_handle.write(imp_as_json)


git_add_commit(
    "imp_no_burdensomeness_no_failure_count.json",
    "IMP without burdensomeness and without failure count",
)

elapsed_time = round(time.time() - start_time, 3)
print(f"converted decorated tasks to IMP;  {elapsed_time} seconds")

############################## ensure IMP-as-JSON adheres to schema ############


json_is_valid = None


json_is_valid = is_valid_json(imp_as_json)

if not json_is_valid:
    print("LLM did not produce valid JSON; try again")

try:
    jsonschema_validate(
        instance=imp_as_json,
        schema=json_schema_for_imp_no_burdensomeness_no_failure_count,
    )
    json_is_valid = True

except jsonschema_ValidationError as err:
    # Catch schema validation errors specifically
    print(
        f"Schema Validation Error:\n{err.message}\n\nFailed at path: {' -> '.join(str(p) for p in err.path)}"
    )
    json_is_valid = False


elapsed_time = round(time.time() - start_time, 3)
print(f"validated JSON for IMP;  {elapsed_time} seconds")
