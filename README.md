# dockerfile-patch

Patch a Dockerfile with a Jinja2 template and build it!

- Author: Asher256
- Email: asher256@gmail.com
- Github repo: https://github.com/Asher256/dockerfile-patch

## What is dockerfile-patch?

dockerfile-patch will allow you to dynamically patch a Dockerfile with Jinja2
templates.

Your Jinja2 templates can be customized using a system facts gatherer that
gather information from Docker images (supported facts: osfamily,
operatingsystem, kernelrelease and architecture). You can use the system facts
to customize the Jinja2 patches you want to apply to your Dockerfiles.

### How does it work?

These are the steps followed by 'dockerfile-patch' to dynamically patch your
Dockerfiles:
- It will load the original (non patched) Dockerfile
- It will detect the Docker image used by the Dockerfile (from the Dockerfile instruction 'FROM')
- It will run the detected docker image and gather system facts (with the script: 'default-facts.sh')
- It will create a patched version of the Dockerfile (a patched Dockerfile means: Jinja2 template is rendered and inserted between the FROM and the rest of the Dockerfile)

## Dependencies
- Read 'requirements.txt' for required dependencies.
- Read 'requirements_optional.txt' for optional dependencies.

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

And we patch it:
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

You can save the patched version below with the '-o' option:
```
dockerfile-patch -o Dockerfile.patched
```

And build the patched version of your container:
```
$ docker build -f Dockerfile.patched -t test:latest  .
```

(You can add the option --debug to the command dockerfile-patch)

The command dockerfile-patch below will render the Jinja patch 'dockerfile-patch.j2'
and insert it after 'FROM' and build the docker container.

This script will help you to patch/template the existing Dockerfiles in order
to add some custom parameters:
- Insert your self signed certificate
- Insert your proxy to download the packages faster during/after the build
- Insert files that are specific to your infrastructure

