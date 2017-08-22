#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: Asher256 <asher256@gmail.com>
# License: GPL
#
# This source code follows the PEP-8 style guide:
# https://www.python.org/dev/peps/pep-0008/
#
"""Patch a Dockerbuild and build it!"""


import sys
import os
import logging
import platform
from subprocess import check_call


assert platform.system() == 'Linux', 'The operating system needs to be Linux'
assert sys.version_info >= (3, 3), "The Python version needs to be >= 3.3"


# DockerPatchBuild will split the file into begin (before DEFAULT_RULE
# Dockerfile commands) and after. The patch will be inserted between the two
# parts.
DEFAULT_RULE = ['CMD', 'ENTRYPOINT']


class DockerfilePatcher(object):
    """Patch a Docker build."""

    def __init__(self, yaml_config):
        """Init the class."""
        self.before = ''
        self.between = ''
        self.after = ''

    def load(self, path):
        """Load the Dockerfile.

        The Dockerfile will be split into 2 parts (before and after
        CMD/ENTRYPOINT).

        """
        pass

    def save(self, path):
        """Save a patched version of the Dockerfile."""
        pass

    def patch(self, lines):
        """Insert lines between the two splits made by self.load()."""
        pass


class DockerPBuild(object):
    """Patch and build a Dockerfile."""

    def __init__(self, facter_script, jinja_patch):
        """Build a Yaml."""
        # this script will start inside any container to retrieve facts
        # it needs to be a /bin/sh script
        self.facter_script = facter_script

        # this jinja patch will be inserted as a patch using DockerfilePatcher
        self.jinja_patch = jinja_patch

    def run_facter(self, image):
        """Run the facter script in an image name."""
        check_call(['docker', 'pull', image])

        host_dir = 'tmpdir'  # TODO: randomize it

        # TODO: randomize it
        host_script_name = 'patch.pbuild'
        host_script = os.path.join(host_dir, host_script_name)

        if not os.path.isdir(host_dir):
            os.mkdir(host_dir)

        with open(host_script, 'w') as fhandler:
            logging.info('Facter script written:\n%s',
                         self.facter_script)
            fhandler.write(self.facter_script)
        os.chmod(host_script, 0o755)

        # TODO: create a random file
        guest_dir = '/pbuild'

        # TODO: create a random file
        guest_script = os.path.join(guest_dir, host_script_name)

        cmd = ['docker', 'run',
               '-v', os.path.abspath(host_dir) + ':' + guest_dir,
               image, '/bin/sh', guest_script]
        logging.info('Run script: %s', ' '.join(cmd))
        check_call(cmd)


def main():
    """The program starts here."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s')

    facter_script = """#!/usr/bin/env sh
if which apt-get >/dev/null 2>&1; then
osfamily=debian
else
osfamily=unknown
fi
echo "osfamily: $osfamily"
"""

    jinja_patch = """{% if osfamily == 'debian' %}
RUN apt-get update    # added by docker-pbuild!
{% endif %}
"""

    pbuild = DockerPBuild(facter_script=facter_script,
                          jinja_patch=jinja_patch)

    print('Facter script:')
    print('==============')
    print(pbuild.facter_script)

    print()
    print('Jinja patch:')
    print('==============')
    print(pbuild.jinja_patch)

    print('Facters:')
    print('========')
    pbuild.run_facter('ubuntu:xenial')

    sys.exit(0)


if __name__ == '__main__':
    main()


# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
