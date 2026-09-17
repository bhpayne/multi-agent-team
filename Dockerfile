FROM phusion/baseimage:jammy-1.0.4

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git python3 python3-pip python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN echo "alias ll='ls -hal'"   >> /etc/bashrc && \
    echo "alias ..='cd ..'"           >> /etc/bashrc && \
    echo "alias s='git status'" >> /etc/bashrc

WORKDIR /opt
COPY requirements.txt /opt
RUN pip3 install -r requirements.txt

COPY run_prompts.py \
     json_schema_for_imp_no_burdensomeness_no_failure_count.json \
     /opt/

#RUN mkdir -p /opt/agent
#WORKDIR /opt/agent
#COPY agent /opt/agent

RUN mkdir -p /opt/git_for_agents
WORKDIR /opt/git_for_agents
RUN git init -b main && \
    git config --global user.email "agents@website.com" && \
    git config --global user.name "TeamOf Agents"

RUN echo "This repository is for the Integrated Master Plan, documentation, generated source code, and other artifacts relevant for coordination with coworkers." > /opt/git_for_agents/README.md

RUN git add README.md && git commit -m "initialized with README"

COPY prompt.md /opt/git_for_agents/users_request.md
RUN git add users_request.md && git commit -m "user's input"

WORKDIR /opt