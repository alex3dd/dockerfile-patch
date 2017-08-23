#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: Asher256 <asher256@gmail.com>
# License: GPL
#
# Github repo: https://github.com/Asher256/docker-pbuild
#
# This source code follows the PEP-8 style guide:
# https://www.python.org/dev/peps/pep-0008/
#
"""docker-pbuild: patch a Dockerfile and build it!

docker-pbuild will help you insert templatable instructions in a Dockerfile
after 'FROM', to build a patched version of a Dockerfile.

Features:
    - Load a Dockerfile and patch it

"""


import sys
import os
import logging
import platform
import tempfile
import signal
import gc
import shutil
from copy import deepcopy
import docker
import yaml
from dockerfile_parse import DockerfileParser


assert platform.system() == 'Linux', 'The operating system needs to be Linux'
assert sys.version_info >= (3, 3), "The Python version needs to be >= 3.3"


class Dockerfile(object):
    """Load a Dockerfile and patch it."""

    def __init__(self):
        """Init the class."""
        # empty DockerfileParser
        self.structure = []
        self.patches = {}

    def load(self, path):
        """Load a Dockerfile."""
        dfp = DockerfileParser(path=path)
        self.structure = deepcopy(dfp.structure)

    def save(self, path, patch=True):
        """Save a patched version of the Dockerfile."""
        with open(path, 'w') as fhandler:
            fhandler.write(self.to_str(patch=patch))

    def get_images(self, image=None):
        """Get all values of FROM in the Dockerfile."""

        result = []
        for item in self.structure:
            if item['instruction'].upper() != 'FROM':
                continue

            if image and item['value'] != image:
                continue

            result.append(item)

        return result

    def set_patch(self, image, content):
        """Patch an image with a Dockerfile content."""
        if image in self.patches:
            raise KeyError("The image '{}' exists already.".format(image))

        self.patches[image.strip()] = content

    def to_str(self, patch=True):
        """Return a patched version of the Dockerfile."""
        result = ''

        # the endlines of all FROM (first endline=0)
        endlines = {}
        for item in self.get_images():
            endlines[item['endline']] = item['value']

        for item in self.structure:
            result += item['content']

            if not patch:
                continue

            if item['instruction'] == 'FROM':
                baseimage = item['value']
                if baseimage in self.patches:
                    patch_comment = '######## docker-pbuild patch for ' + \
                        item['value'] + ' ########\n'
                    result += '\n' + patch_comment + \
                        self.patches[baseimage] + '\n' + patch_comment

        return result


class DockerFacter(object):
    """Patch and build a Dockerfile."""

    def __init__(self, facter_script, jinja_patch):
        """Build a Yaml."""
        # this script will start inside any container to retrieve facts
        # it needs to be a /bin/sh script
        self.facter_script_content = facter_script

        # this jinja patch will be inserted as a patch using DockerfilePatcher
        self.jinja_patch = jinja_patch

    def gather_facts(self, image):
        """Run the facter script in an image name.

        Return: the stdout of the facter script started inside the container
        'image'.

        """
        tmp_prefix = 'docker-pbuild-'
        facter_script_name = 'facter.sh'

        try:
            tmpfiles = {}    # the files in this dict will be deleted

            # create a temporary directory that will contain the facter script
            tmpfiles['host_mpoint'] = tempfile.mkdtemp(suffix='.tmp',
                                                       prefix=tmp_prefix,
                                                       dir='.')
            logging.info('[FACTER] Temporary dir created: %s%s',
                         tmpfiles['host_mpoint'], os.sep)

            facter_script_path = os.path.join(tmpfiles['host_mpoint'],
                                              facter_script_name)

            # create the local facter script
            with open(facter_script_path, 'w') as fhandler:
                logging.info('[FACTER] Facter script written to %s:\n%s',
                             facter_script_path, self.facter_script_content)
                fhandler.write(self.facter_script_content)
            os.chmod(facter_script_path, 0o755)
            logging.info('[FACTER] Temporary file created: %s',
                         facter_script_path)

            docker_client = docker.client.from_env()

            # Guest mount point (volume that points to the local host_mpoint)
            guest_dir = os.path.join('/',
                                     os.path.basename(tmpfiles['host_mpoint']))
            logging.info('[FACTER] Volume in the running Docker container:'
                         ' %s%s', guest_dir, os.sep)
            guest_script = os.path.join(guest_dir, facter_script_name)

            volumes = {os.path.abspath(tmpfiles['host_mpoint']): guest_dir}
            stdout = docker_client.containers.run(image=image,
                                                  command=['/bin/sh',
                                                           guest_script],
                                                  remove=True,
                                                  stdout=True,
                                                  volumes=volumes)
            stdout = stdout.decode('utf-8', 'ignore')

        finally:
            for _, path in tmpfiles.items():
                if os.path.isdir(path):
                    logging.info('[FACTER DELETE] Temporary '
                                 'dir deleted: %s', path)
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    logging.info('[FACTER DELETE] Temporary '
                                 'file deleted: %s', path)
                    os.unlink(path)
                else:
                    logging.info("[FACTER WARNING] Temporary file wasn't "
                                 "found: %s", path)

        return yaml.load(stdout)


def garbage_collector(signum, frame):
    """Garbage collection."""
    gc.collect()
    logging.debug("%s: Garbage collection done.", sys.argv[0])
    if signum == signal.SIGINT:
        sys.stderr.write("Interrupted.\n".format())
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    """The program starts here."""

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s')

    signal.signal(signal.SIGINT, garbage_collector)
    signal.signal(signal.SIGTERM, garbage_collector)

    # First test
    facter_script = """#!/usr/bin/env sh
# Author: Asher256 <asher256@gmail.com>
osfamily=unknown

if which apt-get >/dev/null 2>&1; then
    osfamily=debian
else
    # It is important to redirect it to stderr >&2 to avoid mixing
    # errors with the Yaml returned by this script
    echo "Operating system not detected." >&2
    exit 1
fi
echo "osfamily: $osfamily"
"""

    jinja_patch = """{% if osfamily == 'debian' %}
RUN apt-get update    # added by docker-pbuild!
{% endif %}
"""

    pbuild = DockerFacter(facter_script=facter_script,
                          jinja_patch=jinja_patch)

    print('Facter script:')
    print('==============')
    print(pbuild.facter_script_content)

    print()
    print('Jinja patch:')
    print('==============')
    print(pbuild.jinja_patch)

    print('Facters:')
    print('========')
    facts = pbuild.gather_facts('ubuntu:latest')

    print(facts['osfamily'])

    sys.exit(0)


if __name__ == '__main__':
    main()


# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
