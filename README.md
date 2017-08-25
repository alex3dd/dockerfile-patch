# dockerfile-patch

Patch a Dockerfile using customizable Jinja2 template.

- Author: Achraf Cherti (aka Asher256)
- Email: asher256@gmail.com
- Github repo: https://github.com/Asher256/dockerfile-patch

## What is dockerfile-patch?

dockerfile-patch will allow you to dynamically patch a Dockerfile using Jinja2
templates.

dockerfile-patch can gather system facts from Docker images (supported Docker
image facts: osfamily, operatingsystem, kernelrelease and architecture).
These system facts can be used to customize the Jinja2 templates that are going
to be used to patch your Dockerfile.

## Example

To be able to use dockerfile-patch, you need to add 'dockerfile-patch.j2' to
the same directory as the 'Dockerfile'.

File: dockerfile-patch.j2
```
{% if osfamily == 'Debian' %}
RUN touch /i-patched-this-container
{% endif %}
```

File: Dockerfile
```
FROM ubuntu:latest

# Create a user:test password:test
RUN useradd -m -d /home/test -s /bin/sh test && \
    echo "test:test" | chpasswd

# Standard SSH port
EXPOSE 22

# Run SSH
CMD ["/usr/sbin/sshd", "-D"]
```

And run dockerfile-patch
```
$ dockerfile-patch
FROM ubuntu:latest

######## dockerfile-patch patch for ubuntu:latest ########

RUN touch /i-patched-this-container

######## dockerfile-patch patch for ubuntu:latest ########
RUN useradd -m -d /home/test -s /bin/sh test && \
    echo "test:test" | chpasswd
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]

```

As you can see, the command dockerfile-patch below rendered the Jinja patch
'dockerfile-patch.j2' and inserted it after 'FROM' in the patched Dockerfile.

You can add --debug to show detailed information about the patching process:
```
$ dockerfile-patch --debug
```

To save the patched Dockerfile, use '-o' option:
```
dockerfile-patch -o Dockerfile.patched
```

Once exported, you can build your Docker container using the patched Dockerfile:
```
$ docker build -f Dockerfile.patched -t test:latest  .
```

### How dockerfile-patch it work?

These are the steps followed by 'dockerfile-patch' to dynamically patch your
Dockerfiles:
- It will load the original (not patched) Dockerfile
- It will detect the Docker image used by the Dockerfile (from the Dockerfile instruction 'FROM')
- It will run the detected docker image and gather system facts (with the script: 'default-facts.sh')
- It will create a patched version of the Dockerfile (a patched Dockerfile means: Jinja2 template is rendered and inserted between the FROM and the rest of the Dockerfile)

### Why should I use it dockerfile-patch?

This script will help you to patch/template existing Dockerfiles in order
to add custom parameters:
- Insert your self signed certificate to existing Dockerfiles automatically
- Configure a proxy for apt-get / yum to download the packages faster during the build
- Insert files that are specific to your infrastructure

### Features of dockerfile-path
The features of the current version:
- Load system facts from a Docker image (osfamily)
- Customizable patches with Jinja2 templates. The templates are customizable thanks to the Docker Image system facts
- Auto detect the default default Dockerfile 'USER' and switch to root temporarily before the patch (after the patch, dockerfile-patch will re-switch to the original Dockerfile 'USER')
- Show detailed debug information with --debug
- Output the patch to a file with -o / --output

## Dependencies
- Read 'requirements.txt' for required dependencies.
- Read 'requirements_optional.txt' for optional dependencies.


