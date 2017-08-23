# This Dockerfile is used to test dockerfile-patch
# Github repo: https://github.com/Asher256/dockerfile-patch/

FROM ubuntu:latest
MAINTAINER Asher256 <asher256@gmail.com>

# Install SSH
RUN apt-get -q update && DEBIAN_FRONTEND="noninteractive" apt-get -q install -y openssh-server

# Create a user: test
RUN useradd -m -d /home/test -s /bin/sh test && \
    echo "test:test" | chpasswd

# Standard SSH port
EXPOSE 22

# Run SSH
CMD ["/usr/sbin/sshd", "-D"]
