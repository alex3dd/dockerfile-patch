#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: Asher256 <asher256@gmail.com>
# License: GPL
#
# Github repo: https://github.com/Asher256/docker-pbuild/
#
# This source code follows the PEP-8 style guide:
# https://www.python.org/dev/peps/pep-0008/
#
"""docker-pbuild: patch a Dockerfile and build it!

docker-pbuild will help you insert templatable instructions in a Dockerfile
after 'FROM', to build a patched version of a Dockerfile.

Features:
    - Load a Dockerfile and patch it
    - Load facters from a pulled Docker image

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
from jinja2 import Template


assert platform.system() == 'Linux', 'The operating system needs to be Linux'
assert sys.version_info >= (3, 3), "The Python version needs to be >= 3.3"


class DockerfilePatcher(object):
    """Load a Dockerfile and patch it."""

    def __init__(self):
        """Init the class."""
        # empty DockerfileParser
        self.structure = []
        self.patches = {}

    def load(self, path):
        """Load a Dockerfile."""
        logging.info('[DOCKERFILE PATCHER] Loading: %s',
                     os.path.join(path, 'Dockerfile'))
        dfp = DockerfileParser(path=path)
        self.structure = deepcopy(dfp.structure)

    def save(self, path, patch=True):
        """Save a patched version of the Dockerfile."""
        with open(path, 'w') as fhandler:
            fhandler.write(self.to_str(patch=patch))

    def get_images(self, image=None):
        """Get all values of FROM in the Dockerfile."""

        result = []
        image_names = set()
        for item in self.structure:
            if item['instruction'].upper() != 'FROM':
                continue

            if image and item['value'] != image:
                continue

            result.append(item)
            image_names.add(item['value'])

        logging.info("[DOCKERFILE PATCHER] Base images in the Dockerfile: %s",
                     str(list(image_names)))
        return result

    def set_patch(self, image, content):
        """Patch an image with a Dockerfile content."""
        if image in self.patches:
            raise KeyError("The image '{}' exists already.".format(image))

        logging.info("[DOCKERFILE PATCHER] Patch for '%s' created:\n%s",
                     image, content)
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

    def __init__(self, facter_script):
        """Build a Yaml."""
        # this script will start inside any container to retrieve facts
        # it needs to be a /bin/sh script
        self.facter_script_content = facter_script

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
            logging.info('[FACTS] Temporary dir created: %s%s',
                         tmpfiles['host_mpoint'], os.sep)

            facter_script_path = os.path.join(tmpfiles['host_mpoint'],
                                              facter_script_name)

            # create the local facter script
            with open(facter_script_path, 'w') as fhandler:
                logging.info('[FACTS] Facter script written to %s:\n%s',
                             facter_script_path, self.facter_script_content)
                fhandler.write(self.facter_script_content)
            os.chmod(facter_script_path, 0o755)

            docker_client = docker.client.from_env()

            # Guest mount point (volume that points to the local host_mpoint)
            guest_dir = os.path.join('/',
                                     os.path.basename(tmpfiles['host_mpoint']))
            logging.info('[FACTS] Volume in the running Docker container:'
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
                    logging.info('[FACTS DELETE] Temporary '
                                 'dir deleted: %s', path)
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    logging.info('[FACTS DELETE] Temporary '
                                 'file deleted: %s', path)
                    os.unlink(path)
                else:
                    logging.info("[FACTS WARNING] Temporary file wasn't "
                                 "found: %s", path)

        facts = yaml.load(stdout)
        logging.info('[FACTS] System facts gathered: %s', str(facts))

        return facts


def garbage_collector(signum, frame):
    """Garbage collection."""
    gc.collect()
    logging.debug("%s: Garbage collection done.", sys.argv[0])
    if signum == signal.SIGINT:
        sys.stderr.write("Interrupted.\n".format())
        sys.exit(1)
    else:
        sys.exit(0)


def command_line_interface():
    """The command line interface."""
    # Load the Dockerfile
    dockerfile = DockerfilePatcher()
    dockerfile.load('./test')

    # Load the scripts
    with open('facts.sh', 'r') as fhandler:
        facter_script = fhandler.read()

    with open('test/patch.j2', 'r') as fhandler:
        jinja_patch = fhandler.read()
        logging.info('[FACTS] Jinja patch loaded:\n%s\n',
                     jinja_patch)

    dfacter = DockerFacter(facter_script=facter_script)

    # Gathering facts from all Docker images
    facts = {}
    for item in dockerfile.get_images():
        image_name = item['value']
        if image_name in facts:
            # Already gathered
            continue

        logging.info('[MAIN] Gathering facts from the image: %s', image_name)
        facts[image_name] = dfacter.gather_facts(image_name)

        # Creating the patch for this image
        template = Template(jinja_patch)
        dockerfile.set_patch(image_name, template.render(**facts[image_name]))

    # Final result
    patched_dockerfile = dockerfile.to_str()
    logging.info('[MAIN] FINAL PATCHED Dockerfile:\n%s', patched_dockerfile)


def main():
    """The program starts here."""

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s')

    signal.signal(signal.SIGINT, garbage_collector)
    signal.signal(signal.SIGTERM, garbage_collector)

    command_line_interface()

    sys.exit(0)


if __name__ == '__main__':
    main()


# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
