# This Dockerfile is used to test docker-pbuild 
# Github repo: https://github.com/Asher256/docker-pbuild/

FROM ubuntu:latest
MAINTAINER Asher256 <asher256@gmail.com>

# Install SSH
RUN apt-get -q update && \
    DEBIAN_FRONTEND="noninteractive" apt-get -q install -y -o Dpkg::Options::="--force-confnew" --no-install-recommends openssh &&\
    apt-get -q clean -y && rm -rf /var/lib/apt/lists/* && rm -f /var/cache/apt/*.bin

# Create a user: test
RUN useradd -m -d /home/test -s /bin/sh test && \
    echo "test:test" | chpasswd

# Standard SSH port
EXPOSE 22

# Run SSH
CMD ["/usr/sbin/sshd", "-D"]
