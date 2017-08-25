#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Author: Asher256 <asher256@gmail.com>
# License: GPL
#
# Github repo: https://github.com/Asher256/dockerfile-patch/
#
# This source code follows the PEP-8 style guide:
# https://www.python.org/dev/peps/pep-0008/
#
"""Patch Dockerfiles with Jinja2 templates and Docker images system facts."""


import sys
import os
import logging
import platform
import tempfile
import shutil
import argparse
import signal
import gc
from collections import OrderedDict
from copy import deepcopy
import yaml
import docker
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
        self.logging = logging.getLogger(__name__ + '.' +
                                         self.__class__.__name__)

    def load(self, path):
        """Load a Dockerfile."""
        dfp = DockerfileParser(path=path)
        self.structure = deepcopy(dfp.structure)
        self.logging.debug("[DOCKERFILE PATCHER] '%s' loaded:\n%s",
                           os.path.join(path, 'Dockerfile'),
                           dfp.content)

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

        self.logging.debug("[DOCKERFILE PATCHER] Base images detected in "
                           "the Dockerfile: %s", str(list(image_names)))
        return result

    def set_patch(self, image, content, patch_name=None):
        """Patch an image with a Dockerfile content.

        The most important args are image (the Docker image like
        'ubuntu:latest') and content. 'patch_name' is just a
        string that will be added to the comment before and after
        the patch.

        """
        if image in self.patches:
            raise KeyError("The image '{}' exists already.".format(image))

        self.logging.debug("[DOCKERFILE PATCHER] Patch for '%s' created:\n%s",
                           image, content)
        self.patches[image.strip()] = {'content': content,
                                       'name': patch_name}

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
                    patch = self.patches[baseimage]

                    patch_comment = "#" + ('-' * 8) + " '" + item['value'] + \
                        "' dockerfile-patch:" + ' '
                    if patch['name']:
                        patch_comment += patch['name']

                    patch_comment += ' '
                    patch_comment += ('-' * 8)

                    result += '\n'
                    result += patch_comment
                    result += '\n' + patch['content'] + '\n'
                    result += patch_comment
                    result += '\n' * 2

        return result


class DockerFact(object):
    """Patch and build a Dockerfile."""

    def __init__(self):
        """Build a Yaml."""
        # List of script paths and content: {'path': 'content'}
        self.fact_scripts_paths = OrderedDict()
        # init docker clients
        self.docker_client = docker.client.from_env()
        self.logging = logging.getLogger(__name__ + '.' +
                                         self.__class__.__name__)

    def add_fact_script(self, path):
        """Docstring."""
        with open(path, 'r') as fhandler:
            self.fact_scripts_paths[os.path.abspath(path)] = fhandler.read()

    def gather_facts(self, image):
        """Run the facter script in an image name.

        Return: the stdout of the facter script started inside the container
        'image'.

        """
        # TODO: simplify this function (separate it into parts)
        stdout = ''
        tmp_prefix = 'dockerfile-patch-'

        try:
            tmpfiles = {}    # the files in this dict will be deleted

            # create a temporary directory that will contain the facter script
            tmpfiles['host_mpoint'] = tempfile.mkdtemp(suffix='.tmp',
                                                       prefix=tmp_prefix,
                                                       dir='.')
            self.logging.debug('[FACTS] Temporary dir created: %s%s',
                               tmpfiles['host_mpoint'], os.sep)

            # Guest mount point (volume that points to the local host_mpoint)
            guest_dir = os.path.join('/',
                                     os.path.basename(tmpfiles['host_mpoint']))
            self.logging.debug('[FACTS] Volume in the running '
                               'Docker container:'
                               ' %s%s', guest_dir, os.sep)

            # Write all scripts to the directory
            index = 0
            guest_scripts = []
            for scr_path, scr_content in self.fact_scripts_paths.items():
                index += 1
                facter_script_name = str(index).zfill(6) + "-" + \
                    os.path.basename(scr_path) + '-fact'
                facter_script_path = os.path.join(tmpfiles['host_mpoint'],
                                                  facter_script_name)

                with open(facter_script_path, 'w') as fhandler:
                    self.logging.debug('[FACTS] Fact script '
                                       'written to %s:\n%s',
                                       facter_script_path,
                                       scr_content)
                    fhandler.write(scr_content)
                os.chmod(facter_script_path, 0o755)

                guest_scripts.append(os.path.join(guest_dir,
                                                  facter_script_name))

            # create the main script (this script will run all others)p
            main_script_name = 'main_facter.sh'
            main_script_path = os.path.join(tmpfiles['host_mpoint'],
                                            main_script_name)
            main_script_content = "#!/bin/sh\n"
            main_script_content += 'cd "' + guest_dir + '" || exit 1\n'
            for item in guest_scripts:
                main_script_content += item + " || exit 1\n"
            with open(main_script_path, 'w') as fhandler:
                self.logging.debug('[FACTS] Main facter '
                                   'script written to %s:\n%s',
                                   main_script_path,
                                   main_script_content)
                fhandler.write(main_script_content)
            os.chmod(main_script_path, 0o755)
            guest_main_script = os.path.join(guest_dir, main_script_name)

            # Pull the image
            # self.logging.debug("[FACTS] docker pull '%s'", image)
            sys.stderr.write('[RUN] docker pull {}\n'.format(image))
            sys.stderr.flush()
            self.docker_client.images.pull(image)

            # of 'USER xx' is used, we will switch to root/
            self.logging.debug("[FACTS] docker inspect '%s'", image)
            inspect_image = self.docker_client.api.inspect_image(image)
            image_user = inspect_image['Config']['User'].strip()

            volumes = {os.path.abspath(tmpfiles['host_mpoint']): guest_dir}
            self.docker_client.containers.run(image=image,
                                              command=['/bin/sh',
                                                       guest_main_script],
                                              user='root',
                                              remove=True,
                                              stdout=True,
                                              volumes=volumes)

            facts_yaml = os.path.join(tmpfiles['host_mpoint'],
                                      'facts.yaml')
            try:
                with open(facts_yaml, 'r') as fhandler:
                    stdout = fhandler.read()
            except IOError:
                self.logging.debug("[WARNING] The fact scripts "
                                   "didn't write any fact in '%s'.",
                                   facts_yaml)

        finally:
            for _, path in tmpfiles.items():
                if os.path.isdir(path):
                    self.logging.debug('[FACTS DELETE] Temporary '
                                       'dir deleted: %s%s', path, os.sep)
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    self.logging.debug('[FACTS DELETE] Temporary '
                                       'file deleted: %s', path)
                    os.unlink(path)
                else:
                    self.logging.debug("[FACTS WARNING] Temporary file wasn't "
                                       "found: %s", path)

        facts = yaml.load(stdout)

        # A fact added by dockerfile_patch
        if image_user:
            facts['docker_image_user'] = image_user
        else:
            facts['docker_image_user'] = 'root'

        if not facts:
            self.logging.debug("[FACTS] ERROR: unable to gather facts.")
            sys.exit(1)

        self.logging.debug('[FACTS] System facts gathered: %s', str(facts))

        return facts


def dockerfile_patch(dockerfile_dir, j2_template_path, fact_scripts_paths):
    """The command line interface."""
    logger = logging.getLogger(__name__)

    dockerfile = DockerfilePatcher()
    docker_facter = DockerFact()

    # Load the Dockerfile
    try:
        dockerfile.load(dockerfile_dir)
    except OSError:
        dockerfile_path = os.path.join(dockerfile_dir, 'Dockerfile')
        sys.stderr.write("ERROR: unable to load the Dockerfile "
                         "located in '{}'\n".format(dockerfile_path))
        sys.exit(1)

    # Load the scripts' content into a dict {'path': 'script_content'}
    for item in fact_scripts_paths:
        docker_facter.add_fact_script(path=item)

    try:
        with open(j2_template_path, 'r') as fhandler:
            jinja_patch = fhandler.read()
            logger.debug("[FACTS] Jinja patch '%s' loaded:\n%s\n",
                         j2_template_path, jinja_patch)
    except OSError as err:
        sys.stderr.write("ERROR: unable to load the Jinja2 template "
                         "located in '{}'. {}\n".format(j2_template_path,
                                                        str(err)))
        sys.exit(1)

    # Gathering facts from all Docker images
    facts = {}
    for item in dockerfile.get_images():
        image_name = item['value']
        if image_name in facts:
            # Already gathered
            continue

        logger.debug("[MAIN] Gathering facts from the image '%s'", image_name)
        facts[image_name] = docker_facter.gather_facts(image_name)

        # Creating the patch for this image
        patch = jinja_patch
        if facts[image_name]['docker_image_user'] != 'root':
            # change the user to root before the patch and go back to the
            # Docker image's user after the patch
            patch = '# dockerfile-patch: change the user to root\n' + \
                'USER root\n\n' + \
                "# The patch running as root:\n" + \
                patch + \
                '# dockerfile-patch: go back to the original user\n' + \
                'USER ' + facts[image_name]['docker_image_user'] + '\n'

        template = Template(patch)
        dockerfile.set_patch(image_name, template.render(**facts[image_name]),
                             patch_name=j2_template_path)

    # Final result
    return dockerfile.to_str()


def parse_args():
    """Parse the arguments."""
    description = "Patch a Dockerfile with a Jinja2 template"
    usage = "%(prog)s [--option] [dockerfile_path]"
    parser = argparse.ArgumentParser(description=description,
                                     usage=usage)
    parser.add_argument('path', type=str, nargs='?', default=None,
                        help="The path where the 'Dockerfile' is located.")
    parser.add_argument('-o', '--output', default=None,
                        help='Save the patched Dockerfile to a file')
    parser.add_argument('-c', '--color', action="store_true",
                        default=False, help='Colorize the output')
    parser.add_argument('-d', '--debug', action="store_true",
                        default=False, help='Show debug information')

    args = parser.parse_args()
    debug_format = '%(asctime)s %(name)s: %(message)s'
    if args.debug:
        debug_level = logging.DEBUG

        try:
            from termcolor import colored
            if sys.stdout.isatty():
                debug_format = colored('%(asctime)s %(name)s: ', 'green') \
                    + "%(message)s"
        except ModuleNotFoundError:
            pass
    else:
        debug_level = logging.INFO

    logging.basicConfig(level=debug_level,
                        format=debug_format)

    return args


def garbage_collector(signum, frame):
    """Garbage collection."""
    gc.collect()
    if signum == signal.SIGINT:
        sys.stderr.write("Interrupted.\n".format())
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    """The program starts here."""

    args = parse_args()

    signal.signal(signal.SIGINT, garbage_collector)
    signal.signal(signal.SIGTERM, garbage_collector)

    # default facts gatherer
    default_facts = os.path.join(os.path.dirname(__file__),
                                 'data', 'default-facts.sh')

    # Default parameters
    if args.path:
        dockerfile_dir = args.path
    else:
        dockerfile_dir = '.'

    j2_template_path = os.path.join(dockerfile_dir, 'dockerfile-patch.j2')

    # launch the pbuild script
    output = dockerfile_patch(dockerfile_dir=dockerfile_dir,
                              j2_template_path=j2_template_path,
                              fact_scripts_paths=[default_facts])

    if args.output:
        with open(args.output, 'w') as fhandler:
            fhandler.write(output)
    else:
        sys.stderr.write('[SUCCESS] Patched Dockerfile:\n')
        sys.stderr.flush()

        sys.stdout.write(output)
        sys.stdout.flush()

    sys.exit(0)


if __name__ == '__main__':
    main()

# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
