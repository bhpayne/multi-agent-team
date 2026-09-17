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


def save_token_count_to_file(prompt_summary: str, usage: dict, duration: float) -> None:
    """
    "usage": {
        "prompt_tokens": 932,
        "completion_tokens": 1116,
        "total_tokens": 2048
    }
    """
    with open("/opt/git_for_agents/metrics_token_usage.log", "a") as file_handle:
        file_handle.write('{\n"prompt": "' + prompt_summary + '", ')
        file_handle.write('"prompt tokens": ' + str(usage["prompt_tokens"]) + ", ")
        file_handle.write(
            '"completion tokens": ' + str(usage["completion_tokens"]) + ","
        )
        file_handle.write('"total tokens": ' + str(usage["total_tokens"]) + ",")
        file_handle.write('"duration in seconds": ' + str(duration) + "}\n")
    return


def record_time_in_stage(
    description_of_completed_stage, stage_duration_seconds: float
) -> None:
    with open("/opt/git_for_agents/metrics_stage_durations.log", "a") as file_handle:
        file_handle.write('{"'+
            description_of_completed_stage
            + '": "'
            + str(stage_duration_seconds)
            + ' seconds"}\n'
        )
    return


# Limiting the token count for a local model prevents your computer's
# memory (RAM or VRAM) from overloading and keeps generation speeds usable.
# Default is 2048
max_token_count = 8192  # 16384
# that gets overruled by the parameter specified when the LLM API is launched

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


system_prompt_for_commands = f"""
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


orchestration_start_time = time.time()

############################## brainstorming tasks based on user's request ######

stage_start_time = time.time()
orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
print(f"reading user's request;  {orchestration_elapsed_time} seconds")


with open("git_for_agents/users_request.md", "r") as file_handle:
    users_request = file_handle.read()

system_prompt_for_brainstorming = f"""
Given the user's request below, brainstorm tasks that would be relevant for decomposing the request.


User's request:
```
{users_request}
```
"""

data = {
    "messages": [{"role": "user", "content": system_prompt_for_brainstorming}],
    "max_tokens": max_token_count,
}
prompt_elapsed_time = time.time()
brainstorming_response = requests.post(url, headers=headers, json=data)
prompt_duration = round(time.time() - prompt_elapsed_time,1)

print(json.dumps(brainstorming_response.json(), indent=4))

print("keys:")
print(brainstorming_response.json().keys())

save_token_count_to_file(
    "brainstorming", brainstorming_response.json()["usage"], prompt_duration
)

# If it says "length", it means it hit your max_tokens limit.
# If it says "stop", the model finished generating naturally.
if brainstorming_response.json()["choices"][0]["finish_reason"] == "length":
    print("ERROR: max token count constrained the output")


brainstorming_tasks_md = brainstorming_response.json()["choices"][0]["message"][
    "content"
]

with open("git_for_agents/brainstorming_tasks.md", "w") as file_handle:
    file_handle.write(brainstorming_tasks_md)

git_add_commit("brainstorming_tasks.md", "brainstorming tasks")

orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
print(f"committed brainstorming to git;  {orchestration_elapsed_time} seconds")

stage_elapsed_time = round(time.time() - stage_start_time, 3)
print(f"finished stage of reading user's request;  {stage_elapsed_time} seconds")

record_time_in_stage("finished stage of reading user's request", stage_elapsed_time)

############################## decorate brainstormed tasks with inputs and outputs ############

stage_start_time = time.time()

with open("git_for_agents/brainstorming_tasks.md", "r") as file_handle:
    brainstorming_tasks_md = file_handle.read()

system_prompt_for_decoration_of_tasks = f"""
A few tasks described below have been identified in a brainstorming session. 
For each task add a set of inputs, assumptions, constraints on starting the task.
Also for each task, specify what the expected output of the task is once completed.
Lastly, for each task, estimate how burdensome this task is. Could this be accomplished simply and quickly or would the task be expected to incur multiple subtasks to complete?

Tasks:
```
{brainstorming_tasks_md}
```
"""

data = {
    "messages": [
        {
            "role": "user",
            "content": system_prompt_for_decoration_of_tasks,
        }
    ],
    "max_tokens": max_token_count,
}
prompt_elapsed_time = time.time()
decorated_response = requests.post(url, headers=headers, json=data)
prompt_duration = round(time.time() - prompt_elapsed_time,1)

print(json.dumps(decorated_response.json(), indent=4))


save_token_count_to_file(
    "decoration of tasks", decorated_response.json()["usage"], prompt_duration
)

# If it says "length", it means it hit your max_tokens limit.
# If it says "stop", the model finished generating naturally.
if decorated_response.json()["choices"][0]["finish_reason"] == "length":
    print("ERROR: max token count constrained the output")


decorated_tasks_md = decorated_response.json()["choices"][0]["message"]["content"]

with open("git_for_agents/decorated_tasks.md", "w") as file_handle:
    file_handle.write(decorated_tasks_md)

git_add_commit("decorated_tasks.md", "brainstorming tasks")

orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
print(f"committed decorated tasks to git;  {orchestration_elapsed_time} seconds")

stage_elapsed_time = round(time.time() - stage_start_time, 3)
print(f"finished stage of decorating tasks;  {stage_elapsed_time} seconds")

record_time_in_stage("finished stage of decorating tasks", stage_elapsed_time)

############################## convert decorated tasks into IMP-as-JSON ############

stage_start_time = time.time()

with open("git_for_agents/decorated_tasks.md", "r") as file_handle:
    decorated_tasks_md = file_handle.read()

with open(
    "json_schema_for_imp_no_burdensomeness_no_failure_count.json", "r"
) as file_handle:
    json_schema_for_imp_no_burdensomeness_no_failure_count = file_handle.read()

system_prompt_for_create_IMP = f"""
Convert the tasks into the JSON format specified below 
that captures the sequence of tasks and the dependencies among tasks.
The nodes of the graph are tasks, and the directed edges indicate the order in which to do tasks. 
The predecessor task is the key, the subsequent task is the value in the edge dictionary.

For each task in the JSON file fill in the "task description", 
"inputs needed for task", "assumptions about the task", 
"constraints on the task", and "expected output from the task".
The "id" value is a distinct string that is used to label the task node and is used in the edge dictionary.

For the "inputs needed for task" describe the parameters or documents; do not refer to the task IDs.

The JSON file must adhere to the schema below. 
```
{json_schema_for_imp_no_burdensomeness_no_failure_count}
```

Do not include markdown code blocks, conversational filler, or explanations. 

Tasks:
```
{decorated_tasks_md}
```
"""

data = {
    "messages": [
        {
            "role": "user",
            "content": system_prompt_for_create_IMP,
        }
    ],
    "response_format": {"type": "json_object"},
    "temperature": 0.2,  # Lower temperature reduces creativity and formatting mistakes
    "max_tokens": max_token_count,
}
prompt_elapsed_time = time.time()
imp_response = requests.post(url, headers=headers, json=data)
prompt_duration = round(time.time() - prompt_elapsed_time,1)

# print(json.dumps(imp_response.json(), indent=4))


save_token_count_to_file(
    "IMP-as-JSON from decorated tasks", imp_response.json()["usage"], prompt_duration
)


# If it says "length", it means it hit your max_tokens limit.
# If it says "stop", the model finished generating naturally.
if imp_response.json()["choices"][0]["finish_reason"] == "length":
    print("ERROR: max token count constrained the output")


imp_as_json_str = imp_response.json()["choices"][0]["message"]["content"]

print("IMP as JSON:")
print(imp_as_json_str)

with open(
    "git_for_agents/imp_no_burdensomeness_no_failure_count.json", "w"
) as file_handle:
    file_handle.write(imp_as_json_str)


git_add_commit(
    "imp_no_burdensomeness_no_failure_count.json",
    "IMP without burdensomeness and without failure count",
)

orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
print(f"converted decorated tasks to IMP;  {orchestration_elapsed_time} seconds")

stage_elapsed_time = round(time.time() - stage_start_time, 3)
print(f"finished stage of decorated tasks to IMP JSON;  {stage_elapsed_time} seconds")

record_time_in_stage(
    "finished stage of decorated tasks to IMP JSON", stage_elapsed_time
)

############################## ensure IMP-as-JSON is JSON ############

stage_start_time = time.time()

json_is_valid = None

json_is_valid = is_valid_json(imp_as_json_str)

if not json_is_valid:
    print("ERROR: LLM did not produce valid JSON; try again")

############################## ensure IMP-as-JSON adheres to schema ############

stage_start_time = time.time()

imp_as_json = json.loads(imp_as_json_str)

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
except TypeError as err:
    print(f"Error:\n{str(err)}")
    json_is_valid = False


orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
if orchestration_elapsed_time < 120:
    print(f"validated JSON for IMP;  {orchestration_elapsed_time} seconds")
else:
    print(f"validated JSON for IMP;  {orchestration_elapsed_time/60} minutes")

stage_elapsed_time = round(time.time() - stage_start_time, 3)
if stage_elapsed_time < 120:
    print(f"finished stage of validated IMP JSON;  {stage_elapsed_time} seconds")
else:
    print(f"finished stage of validated IMP JSON;  {stage_elapsed_time/60} minutes")

##################### IMP-as-JSON to Graphviz ##########

stage_start_time = time.time()

with open(
    "/opt/git_for_agents/imp_no_burdensomeness_no_failure_count.json", "r"
) as file_handle:
    imp_as_json = json.load(file_handle)

if "dependencies" in imp_as_json.keys():
    task_dependencies = imp_as_json["dependencies"]

    system_prompt_for_IMP_to_graphviz = f"""
    Given this set of dependencies, create a Graphviz directed graph. 

    ```
    {task_dependencies}
    ```
    """

    data = {
        "messages": [
            {
                "role": "user",
                "content": system_prompt_for_IMP_to_graphviz,
            }
        ],
    }
    prompt_elapsed_time = time.time()
    imp_graphviz_response = requests.post(url, headers=headers, json=data)
    prompt_duration = round(time.time() - prompt_elapsed_time,1)

    # print(json.dumps(imp_graphviz_response.json(), indent=4))

    save_token_count_to_file(
        "IMP to Graphviz", imp_graphviz_response.json()["usage"], prompt_duration
    )

    # If it says "length", it means it hit your max_tokens limit.
    # If it says "stop", the model finished generating naturally.
    if imp_graphviz_response.json()["choices"][0]["finish_reason"] == "length":
        print("ERROR: max token count constrained the output")

    imp_as_graphviz = imp_graphviz_response.json()["choices"][0]["message"]["content"]

    print("IMP as Graphviz:")
    print(imp_as_graphviz)

    orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
    if orchestration_elapsed_time < 120:
        print(f"IMP to Graphviz;  {orchestration_elapsed_time} seconds")
    else:
        print(f"IMP to Graphviz;  {orchestration_elapsed_time/60} minutes")

    stage_elapsed_time = round(time.time() - stage_start_time, 3)
    if stage_elapsed_time < 120:
        print(f"finished stage of IMP to Graphviz;  {stage_elapsed_time} seconds")
    else:
        print(f"finished stage of IMP to Graphviz;  {stage_elapsed_time/60} minutes")


else:
    print("'dependencies' was not present in the IMP JSON")
