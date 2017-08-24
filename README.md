# dockerfile-patch

Patch a Dockerfile and build it!

- Author: Asher256
- Email: asher256@gmail.com
- Github repo: https://github.com/Asher256/dockerfile-patch

## Dependencies
Read 'requirements.txt'.

## Example

The './dockerfile-patch.j2' file:
```
{% if osfamily == 'Debian' %}
RUN touch /i-patched-this-container
{% endif %}
```

The './Dockerfile' file:
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

And run 'dockerfile-patch' with the same parameters as 'docker build':
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

