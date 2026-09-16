
# Get the machine architecture.
# On arm64 (Apple Silicon M1/M2/etc.), `uname -m` outputs "arm64".
# On amd64 (Intel), `uname -m` outputs "x86_64".
ARCH := $(shell uname -m)

ifeq ($(ARCH), arm64)
        this_arch=arm64
else ifeq ($(ARCH), x86_64)
        this_arch=amd64
else
        @echo "Unknown architecture: $(ARCH). Cannot determine if Mac is new (arm64) or old (amd64)."
endif

ISOLATION_IMAGE=phusion-jammy

CONTAINER_TAG=latest-$(this_arch)

DOCKER_OR_PODMAN=docker


container_build:
	$(DOCKER_OR_PODMAN) build -t $(ISOLATION_IMAGE):$(CONTAINER_TAG) .

# don't include
#                 -v `pwd`:/scratch -w /scratch/ \
# unless agents should have access to host
# 
# The host mapping
#                 --add-host=host.docker.internal:host-gateway \
# is for linux; not needed on Mac
container_live_user:
	$(DOCKER_OR_PODMAN) run -it --rm \
                --publish 8000:8000 \
                --add-host=host.docker.internal:host-gateway \
                --user $$(id -u):$$(id -g) \
                $(ISOLATION_IMAGE):$(CONTAINER_TAG) /bin/bash

container_live_root:
	$(DOCKER_OR_PODMAN) run -it --rm \
                --publish 8000:8000 \
                -v `pwd`:/scratch -w /scratch/ \
                --add-host=host.docker.internal:host-gateway \
                $(ISOLATION_IMAGE):$(CONTAINER_TAG) /bin/bash

# assumes the webserver is already running
container_shell:
	$(DOCKER_OR_PODMAN) exec -it $$(docker ps -qf "name=phusion") /bin/bash


