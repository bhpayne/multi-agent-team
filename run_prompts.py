#!/usr/bin/env python3

import os
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
        file_handle.write('{"prompt": "' + prompt_summary + '", ')
        file_handle.write('"prompt tokens": ' + str(usage["prompt_tokens"]) + ", ")
        file_handle.write(
            '"completion tokens": ' + str(usage["completion_tokens"]) + ","
        )
        file_handle.write('"total tokens": ' + str(usage["total_tokens"]) + ",")
        file_handle.write('"duration in seconds": ' + str(duration) + "}\n")
    return


def print_duration(
    orchestration_start_time, stage_start_time, stage_label: str
) -> None:

    orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
    if orchestration_elapsed_time < 120:
        print(
            f"reached {stage_label} in cumulative  {orchestration_elapsed_time} seconds"
        )
    else:
        print(
            f"reached {stage_label} in cumulative  {orchestration_elapsed_time/60} minutes"
        )

    stage_elapsed_time = round(time.time() - stage_start_time, 3)
    if stage_elapsed_time < 120:
        print(f"finished stage {stage_label} in {stage_elapsed_time} seconds")
    else:
        print(f"finished stage {stage_label} in {stage_elapsed_time/60} minutes")
    return

    with open("/opt/git_for_agents/metrics_stage_durations.log", "a") as file_handle:
        file_handle.write(
            '{"' + stage_label + '": "' + str(stage_duration_seconds) + ' seconds"}\n'
        )


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

stage_description = "brainstorming"

orchestration_elapsed_time = round(time.time() - orchestration_start_time, 3)
print(f"reading user's request;  {orchestration_elapsed_time} seconds")


with open("/opt/git_for_agents/users_request.md", "r") as file_handle:
    users_request = file_handle.read()

system_prompt_for_brainstorming = f"""
Given the user's request below, brainstorm tasks that would be relevant for decomposing the request.

User's request:
```
{users_request}
```
"""


with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/prompt_for_"
    + stage_description
    + ".md",
    "w",
) as file_handle:
    file_handle.write(system_prompt_for_brainstorming)

data = {
    "messages": [{"role": "user", "content": system_prompt_for_brainstorming}],
    "max_tokens": max_token_count,
}
prompt_elapsed_time = time.time()
brainstorming_response = requests.post(url, headers=headers, json=data)
prompt_duration = round(time.time() - prompt_elapsed_time, 1)

with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/result_from_"
    + stage_description
    + ".json",
    "w",
) as file_handle:
    json.dump(brainstorming_response.json(), file_handle, indent=2)

# print("keys:")
# print(brainstorming_response.json().keys())

save_token_count_to_file(
    stage_description, brainstorming_response.json()["usage"], prompt_duration
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

git_add_commit("brainstorming_tasks.md", stage_description)

print_duration(orchestration_start_time, stage_start_time, stage_description)


############################## decorate brainstormed tasks with inputs and outputs ############

stage_start_time = time.time()

stage_description = "decoration of tasks"

with open("git_for_agents/brainstorming_tasks.md", "r") as file_handle:
    brainstorming_tasks_md = file_handle.read()

system_prompt_for_decoration_of_tasks = f"""
For each task add 
- a set of expected inputs, like required files or values
- assumptions made about the task
- constraints on starting the task.
- specify what the expected output of the task is once completed.

Tasks:
```
{brainstorming_tasks_md}
```
"""

with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/prompt_for_"
    + stage_description
    + ".md",
    "w",
) as file_handle:
    file_handle.write(system_prompt_for_decoration_of_tasks)

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
prompt_duration = round(time.time() - prompt_elapsed_time, 1)

with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/result_from_"
    + stage_description
    + ".json",
    "w",
) as file_handle:
    json.dump(decorated_response.json(), file_handle, indent=2)

try:
    save_token_count_to_file(
        stage_description, decorated_response.json()["usage"], prompt_duration
    )
except KeyError as err:
    print("ERROR: 'usage' missing from decorated_response")
    print(str(decorated_response.json()))

# If it says "length", it means it hit your max_tokens limit.
# If it says "stop", the model finished generating naturally.
if decorated_response.json()["choices"][0]["finish_reason"] == "length":
    print("ERROR: max token count constrained the output")


decorated_tasks_md = decorated_response.json()["choices"][0]["message"]["content"]

with open("git_for_agents/decorated_tasks.md", "w") as file_handle:
    file_handle.write(decorated_tasks_md)

git_add_commit("decorated_tasks.md", stage_description)

print_duration(orchestration_start_time, stage_start_time, stage_description)


############################## convert decorated tasks into IMP-as-JSON ############

stage_start_time = time.time()

stage_description = "IMP-as-JSON from decorated tasks"

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

with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/prompt_for_"
    + stage_description
    + ".md",
    "w",
) as file_handle:
    file_handle.write(system_prompt_for_create_IMP)

git_add_commit(
    "logging_of_prompts_and_results/prompt_for_" + stage_description + ".md",
    stage_description,
)

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
prompt_duration = round(time.time() - prompt_elapsed_time, 1)

with open(
    "/opt/git_for_agents/logging_of_prompts_and_results/result_from_"
    + stage_description
    + ".json",
    "w",
) as file_handle:
    json.dump(imp_response.json(), file_handle, indent=2)

# print(json.dumps(imp_response.json(), indent=4))


save_token_count_to_file(
    stage_description, imp_response.json()["usage"], prompt_duration
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
    stage_description,
)

print_duration(orchestration_start_time, stage_start_time, stage_description)


############################## ensure IMP-as-JSON is JSON ############

stage_start_time = time.time()

json_is_valid = None

json_is_valid = is_valid_json(imp_as_json_str)

if not json_is_valid:
    print("ERROR: LLM did not produce valid JSON; try again")

############################## ensure IMP-as-JSON adheres to schema ############

stage_start_time = time.time()

stage_description = "JSON for IMP"

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


print_duration(orchestration_start_time, stage_start_time, stage_description)

##################### IMP-as-JSON to Graphviz ##########

stage_start_time = time.time()

stage_description = "IMP to Graphviz"

with open(
    "/opt/git_for_agents/imp_no_burdensomeness_no_failure_count.json", "r"
) as file_handle:
    imp_as_json = json.load(file_handle)

if "dependencies" in imp_as_json.keys():
    task_dependencies = imp_as_json["dependencies"]

    system_prompt_for_IMP_to_graphviz = f"""
Given this set of dependencies, create a Graphviz directed graph. 

Do not include markdown code blocks, conversational filler, or explanations. 


```
{task_dependencies}
```
    """

    with open(
        "/opt/git_for_agents/logging_of_prompts_and_results/prompt_for_"
        + stage_description
        + ".md",
        "w",
    ) as file_handle:
        file_handle.write(system_prompt_for_IMP_to_graphviz)

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
    prompt_duration = round(time.time() - prompt_elapsed_time, 1)

    # print(json.dumps(imp_graphviz_response.json(), indent=4))

    with open(
        "/opt/git_for_agents/logging_of_prompts_and_results/result_from_"
        + stage_description
        + ".json",
        "w",
    ) as file_handle:
        json.dump(imp_graphviz_response.json(), file_handle, indent=2)

    save_token_count_to_file(
        stage_description, imp_graphviz_response.json()["usage"], prompt_duration
    )

    # If it says "length", it means it hit your max_tokens limit.
    # If it says "stop", the model finished generating naturally.
    if imp_graphviz_response.json()["choices"][0]["finish_reason"] == "length":
        print("ERROR: max token count constrained the output")

    imp_as_graphviz = imp_graphviz_response.json()["choices"][0]["message"]["content"]

    print("IMP as Graphviz:")
    print(imp_as_graphviz)

    with open("/opt/git_for_agents/imp_as_graphviz.gv", "w") as file_handle:
        file_handle.write(imp_as_graphviz)

    print_duration(orchestration_start_time, stage_start_time, stage_description)


else:
    print("'dependencies' was not present in the IMP JSON")


##################### add burdensomeness to IMP-as-JSON ########

stage_start_time = time.time()

stage_description = "IMP all fields"

with open(
    "/opt/git_for_agents/imp_no_burdensomeness_no_failure_count.json", "r"
) as file_handle:
    imp_no_burdensomeness = json.load(file_handle)


for task_index, entry in enumerate(imp_no_burdensomeness["tasks"]):

    system_prompt_for_task_burdensomeness = f"""
estimate how burdensome this task is. Could this be accomplished simply and quickly or 
would the task be expected to incur multiple subtasks to complete?

Respond with one of the following in JSON format: 
- burdensomeness: "simple task"
- burdensomeness: "multi-step task"

Here's the task to assess:
```
{entry}
```
    """

    with open(
        "/opt/git_for_agents/logging_of_prompts_and_results/prompt_for_"
        + stage_description
        + "_"
        + str(task_index)
        + ".md",
        "w",
    ) as file_handle:
        file_handle.write(system_prompt_for_task_burdensomeness)

    data = {
        "messages": [
            {
                "role": "user",
                "content": system_prompt_for_task_burdensomeness,
            }
        ],
        "response_format": {"type": "json_object"},
    }
    prompt_elapsed_time = time.time()
    burdensomeness_response = requests.post(url, headers=headers, json=data)
    prompt_duration = round(time.time() - prompt_elapsed_time, 1)

    # print(json.dumps(burdensomeness.json(), indent=4))

    with open(
        "/opt/git_for_agents/logging_of_prompts_and_results/result_from_"
        + stage_description
        + "_"
        + str(task_index)
        + ".json",
        "w",
    ) as file_handle:
        json.dump(burdensomeness_response.json(), file_handle, indent=2)

    save_token_count_to_file(
        "IMP task burdensomeness " + str(task_index),
        burdensomeness_response.json()["usage"],
        prompt_duration,
    )

    # If it says "length", it means it hit your max_tokens limit.
    # If it says "stop", the model finished generating naturally.
    if burdensomeness_response.json()["choices"][0]["finish_reason"] == "length":
        print("ERROR: max token count constrained the output")

    burdensomeness_as_json_str = burdensomeness_response.json()["choices"][0][
        "message"
    ]["content"]

    # print("burdensomeness_as_json_str:")
    # print(burdensomeness_as_json_str)

    try:
        burdensomeness_dict = json.loads(burdensomeness_as_json_str)
    except json.JSONDecodeError as err:
        # Handles malformed JSON strings (e.g., missing quotes, trailing commas)
        print(f"ERROR: Invalid JSON string format: {err}")
        burdensomeness_dict = {"burdensomeness": "TBD"}
    except TypeError as err:
        # Handles cases where the input is not a string or bytes object (e.g., None, int, dict)
        print(f"ERROR: Input must be a string or bytes-like object: {err}")
        burdensomeness_dict = {"burdensomeness": "TBD"}

    imp_no_burdensomeness["tasks"][task_index]["burdensomeness"] = burdensomeness_dict[
        "burdensomeness"
    ]
    imp_no_burdensomeness["tasks"][task_index]["status"] = "not yet started"
    imp_no_burdensomeness["tasks"][task_index]["failure counter"] = 0

with open("/opt/git_for_agents/imp.json", "w") as file_handle:
    json.dump(imp_no_burdensomeness, file_handle, indent=2)

git_add_commit(
    "imp.json",
    stage_description,
)

print_duration(orchestration_start_time, stage_start_time, stage_description)


################################### create folders per task

stage_start_time = time.time()

stage_description = "write task into folder"


with open("/opt/git_for_agents/imp.json", "r") as file_handle:
    imp_as_json = json.load(file_handle)

for entry in imp_as_json["tasks"]:
    folder_name = entry["id"] + "_" + entry["task description"]

    full_path = "/opt/git_for_agents/tasks/" + folder_name
    os.mkdir(full_path)

    with open(full_path + "/task_description.json", "w") as file_handle:
        json.dump(imp_as_json, file_handle, indent=2)


print_duration(orchestration_start_time, stage_start_time, stage_description)

###################################
