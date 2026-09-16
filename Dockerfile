FROM phusion/baseimage:jammy-1.0.4

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git python3 python3-pip python3-dev

RUN mkdir -p /opt/agent
WORKDIR /opt/agent
COPY agent /opt/agent

RUN mkdir -p /opt/git_for_agents
WORKDIR /opt/git_for_agents
RUN git init -b main

RUN echo "This repository is for the Integrated Master Plan, documentation, generated source code, and other artifacts relevant for coordination with coworkers." > /opt/git_for_agents/README.md

RUN git add README.md && git commit -m "initialized with README"


