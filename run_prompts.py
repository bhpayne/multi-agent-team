#!/usr/bin/env python3

import requests
import json

url = "http://host.docker.internal:8000/v1/chat/completions"

headers = {"Content-Type": "application/json"}


available_commands = ["apt","awk","basename",
                "bc","break","cat","cd",
             "chgrp","chmod","chown","continue",
           "cp","curl","date","diff",
"dmesg","do","du","echo","elif","else","export","fi","find","for","gh","git","glab","grep","head","hostname","if","ifconfig","ls","mkdir","mv","netstat","ping","pip3","podman","pwd","python3","rm","sed","sort","ssh-keygen","ssh","tail","time","touch","tr","wc","wget","xargs"]

with open('git_for_agents/users_request.md', 'r') as file_handle:
    users_request = file_handle.read()


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


data = {
    "messages": [
        {"role": "user", 
         "content": system_prompt_for_brainstorming + users_request}
    ]
}
response = requests.post(url, headers=headers, json=data)

print(json.dumps(response.json(), indent=4))

print(response.json()['choices'][0]['message']['content'])
