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
        self.patches = []
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

    def add_patch(self, image, content, patch_name=None):
        """Patch an image with a Dockerfile content.

        The most important args are image (the Docker image like
        'ubuntu:latest') and content. 'patch_name' is just a
        string that will be added to the comment before and after
        the patch.

        patch_name needs to be unique (it is going to be a key in a dict).
        Same thing with 'image' parameter.

        """
        if image in self.patches:
            raise KeyError("The image '{}' exists already.".format(image))

        self.logging.debug("[DOCKERFILE PATCHER] Patch for '%s' created:\n%s",
                           image, content)

        image = image.strip()
        self.patches.append({'image': image,
                             'patch_name': patch_name,
                             'content': content})

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
                # baseimage = item['value']
                for patch_item in self.patches:
                    patch_comment = "#" + ('-' * 8) + " '" + \
                        item['value'] + \
                        "' dockerfile-patch"

                    if patch_item['patch_name']:
                        patch_comment += ': ' + patch_item['patch_name']

                    patch_comment += ' '
                    patch_comment += ('-' * 8)

                    result += '\n'
                    result += patch_comment
                    result += '\n' + patch_item['content'] + '\n'
                    result += patch_comment
                    result += '\n' * 2

        return result


class DockerFact(object):
    """Patch and build a Dockerfile."""

    def __init__(self):
        """Build a Yaml."""
        # these files will be deleted
        self.tmpfiles = []
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

    def gather_facts(self, image, tmp_dir='.'):
        """Run the facter script in an image name.

        Return: the stdout of the facter script started inside the container
        'image'.

        tmp_prefix: the directory where the temporary file will be created
        (default = '.').

        """
        # TODO: simplify this function (separate it into parts)
        stdout = ''
        tmp_prefix = 'dockerfile-patch-'

        # create a temporary directory that will contain the facter script
        host_mpoint = tempfile.mkdtemp(suffix='.tmp',
                                       prefix=tmp_prefix,
                                       dir=tmp_dir)
        self.tmpfiles.append(host_mpoint)
        self.logging.debug('[FACTS] Temporary dir created: %s%s',
                           host_mpoint, os.sep)

        # Guest mount point (volume that points to the local host_mpoint)
        guest_dir = os.path.join('/',
                                 os.path.basename(host_mpoint))
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
            facter_script_path = os.path.join(host_mpoint,
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
        main_script_path = os.path.join(host_mpoint,
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

        volumes = {os.path.abspath(host_mpoint): guest_dir}
        self.docker_client.containers.run(image=image,
                                          command=['/bin/sh',
                                                   guest_main_script],
                                          user='root',
                                          remove=True,
                                          stdout=True,
                                          volumes=volumes)

        facts_yaml = os.path.join(host_mpoint,
                                  'facts.yaml')
        try:
            with open(facts_yaml, 'r') as fhandler:
                stdout = fhandler.read()
        except IOError:
            self.logging.debug("[WARNING] The fact scripts "
                               "didn't write any fact in '%s'.",
                               facts_yaml)

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

        # delete temporary files
        self._rm_tmpfiles()

        return facts

    def __del__(self):
        """Clean-up."""
        self._rm_tmpfiles()

    def _rm_tmpfiles(self):
        """Delete temporary files."""
        for path in self.tmpfiles:
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

        # it is empty now
        self.tmpfiles = []


def dockerfile_patch(dockerfile_dir, jinja2_patches_paths, fact_scripts_paths):
    """The command line interface.

    Params:
        dockerfile_dir: directory where the Dockerfile is stored
        jinja2_patches_paths: list of paths to Jinja2 templates
        fact_scripts_paths: list of paths to fact scripts

    """
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

    # Load multiple patches
    jinja_patches_content = []
    for item in jinja2_patches_paths:
        try:
            with open(item, 'r') as fhandler:
                current_content = fhandler.read()
                jinja_patches_content.append({'path': item,
                                              'content': current_content})

                logger.debug("[FACTS] Jinja patch '%s' loaded:\n%s\n",
                             item, current_content)
        except OSError as err:
            sys.stderr.write("ERROR: unable to load the Jinja2 template "
                             "located in '{}'. {}\n".format(item,
                                                            str(err)))
            sys.exit(1)

    # Gathering facts from all Docker images
    facts = {}
    for item_image in dockerfile.get_images():
        image_name = item_image['value']
        if image_name in facts:
            # Already gathered
            continue

        logger.debug("[MAIN] Gathering facts from the image '%s'", image_name)
        facts[image_name] = docker_facter.gather_facts(image_name,
                                                       tmp_dir=dockerfile_dir)

        # Creating the patch for this image
        patch = ''
        for item_j2_data in jinja_patches_content:
            template = Template(item_j2_data['content'])
            patch += '\n'
            patch += '#\n'
            patch += '# ==> Patch: ' + item_j2_data['path'] + '\n'
            patch += '#\n'
            patch += template.render(**facts[image_name]).strip() + '\n'

        # to the user switch (USER root, ..., USER previous_user)
        if facts[image_name]['docker_image_user'] != 'root':
            # change the user to root before the patch and go back to the
            # Docker image's user after the patch
            patch += '# dockerfile-patch: change the user to root\n' + \
                'USER root\n\n' + \
                "# The patch running as root:\n" + \
                patch + \
                '# dockerfile-patch: go back to the original user\n' + \
                'USER ' + facts[image_name]['docker_image_user'] + '\n'

        dockerfile.add_patch(image_name, patch)

    # Final result
    return dockerfile.to_str()


def parse_args():
    """Parse the arguments."""
    # default template
    description = "Patch a Dockerfile with a Jinja2 template"
    usage = "%(prog)s [--option] [dockerfile_path]"
    parser = argparse.ArgumentParser(description=description,
                                     usage=usage)
    parser.add_argument('path', type=str, nargs='?', default=None,
                        help="The path where the 'Dockerfile' is located.")
    parser.add_argument('-p', '--patch', action='append', required=True,
                        help='Path to the Jinja2 patch (can be '
                        'specified multiple times)')
    parser.add_argument('-o', '--output', default=None,
                        help='A file where the patched '
                        'Dockerfile will be saved')
    parser.add_argument('-c', '--color', action="store_true",
                        default=False, help='Colorize the output '
                        'when --debug is activated')
    parser.add_argument('-d', '--debug', action="store_true",
                        default=False, help='Show more information '
                        'during the patching process')

    args = parser.parse_args()
    debug_format = '%(asctime)s %(name)s: %(message)s'
    if args.debug:
        debug_level = logging.DEBUG

        if args.color:
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

    # launch the pbuild script
    output = dockerfile_patch(dockerfile_dir=dockerfile_dir,
                              jinja2_patches_paths=args.patch,
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

# quicktest: python3 % -p ../test/dockerfile-patch.j2
# quicktest: -p ../test/dockerfile-patch.j2
# quicktest: -p ../test/dockerfile-patch.j2 ../test
# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
