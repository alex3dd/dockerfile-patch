# dockerfile-patch

Patch your Dockerfiles with customizable Jinja2 templates.

- Author: Achraf Cherti (aka Asher256)
- Email: asher256@gmail.com
- Github repo: https://github.com/Asher256/dockerfile-patch

## How to install dockerfile-patch?
```
pip install git+https://github.com/Asher256/dockerfile-patch
```

## What is dockerfile-patch?

dockerfile-patch will allow you to dynamically patch a Dockerfile using Jinja2
templates.

dockerfile-patch can gather system facts from Docker images (supported Docker
image facts: osfamily, operatingsystem, kernelrelease and architecture).

The system facts gathered can be used to patch your Dockerfile with a Jinja2
template. The Jinja2 template can use the facts to render a customized patch
between 'FROM image:release' and the reste of your Dockerfile.

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
$ dockerfile-patch -p dockerfile-patch.j2
[RUN] docker pull ubuntu:latest
[SUCCESS] Patched Dockerfile:
FROM ubuntu:latest

######## dockerfile-patch patch for ubuntu:latest ########

RUN touch /i-patched-this-container

######## dockerfile-patch patch for ubuntu:latest ########
RUN useradd -m -d /home/test -s /bin/sh test && \
    echo "test:test" | chpasswd
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]

```

You can hide stderr to show the patched Dockerfile only:
```
$ dockerfile-patch -p dockerfile-patch.j2 2>/dev/null
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
$ dockerfile-patch -p dockerfile-patch.j2 --debug
```

To save the patched Dockerfile, use '-o' option:
```
$ dockerfile-patch -p dockerfile-patch.j2 -o Dockerfile.patched
```

Once exported, you can build your Docker container using the patched Dockerfile:
```
$ docker build -f Dockerfile.patched -t test:latest  .
```

### How dockerfile-patch it work?

These are the steps followed by 'dockerfile-patch' to dynamically patch your
Dockerfiles:
- Load the original Dockerfile
- Detect the Docker image in the Dockerfile (using 'FROM' instruction)
- Run the detected docker image and gather system facts (with the script: 'default-facts.sh')
- Create a patched version of the Dockerfile (a patched Dockerfile means: a Jinja2 template is rendered and inserted between 'FROM image:release' and the rest of the Dockerfile)

### Why should I use it dockerfile-patch?

dockerfile-patch will help you to patch existing Dockerfiles in order to add
custom parameters specific to your needs:
- **Inject your self-signed certificate into an existing Dockerfile**. Why? Because
  you don't want to add a self-signed configuration to all Dockerfiles you
  create. Your Dockerfiles will remain clean and the patching process will be
  done automatically thanks to dockerfile-patch and your continuous integration
  tool.
- Dynamically add a proxy parameter to apt-get to speed up the download
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


