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
"""dockerfile-patch: patch a Dockerfile and build it!

dockerfile-patch will help you insert templatable instructions in a Dockerfile
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
import argparse
from collections import OrderedDict
from copy import deepcopy
from subprocess import Popen, CalledProcessError
import yaml
import docker
from dockerfile_parse import DockerfileParser
from jinja2 import Template


assert platform.system() == 'Linux', 'The operating system needs to be Linux'
assert sys.version_info >= (3, 3), "The Python version needs to be >= 3.3"


class OldDocker(object):
    """Wrapper around 'docker' command."""

    def __init__(self, timeout=None):
        """Init the Docker class."""
        self.timeout = timeout

    def __call__(self, args, *popen_args, **popen_kwargs):
        """Same as subprocess.Popen() (except the first one: args)."""
        assert isinstance(args, list), \
            "The type of 'args' needs to be 'list'"
        cmd = ['docker'] + args
        logging.info('[RUN COMMAND] %s', ' '.join(cmd))
        proc = Popen(args=cmd, *popen_args, **popen_kwargs)
        (stdout, stderr) = proc.communicate(timeout=self.timeout)
        if proc.returncode != 0:
            raise CalledProcessError(returncode=proc.returncode,
                                     cmd=cmd,
                                     output=stdout,
                                     stderr=stderr)

        if stdout:
            stdout = stdout.decode('utf-8', 'ignore')
        else:
            stdout = ''

        if stderr:
            stderr = stderr.decode('utf-8', 'ignore')
        else:
            # None because stdout is not PIPE
            stderr = ''

        return stdout, stderr


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

    def set_patch(self, image, content, patch_name=None):
        """Patch an image with a Dockerfile content.

        The most important args are image (the Docker image like
        'ubuntu:latest') and content. 'patch_name' is just a
        string that will be added to the comment before and after
        the patch.

        """
        if image in self.patches:
            raise KeyError("The image '{}' exists already.".format(image))

        logging.info("[DOCKERFILE PATCHER] Patch for '%s' created:\n%s",
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
            logging.info('[FACTS] Temporary dir created: %s%s',
                         tmpfiles['host_mpoint'], os.sep)

            # Guest mount point (volume that points to the local host_mpoint)
            guest_dir = os.path.join('/',
                                     os.path.basename(tmpfiles['host_mpoint']))
            logging.info('[FACTS] Volume in the running Docker container:'
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
                    logging.info('[FACTS] Fact script written to %s:\n%s',
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
                logging.info('[FACTS] Main facter script written to %s:\n%s',
                             main_script_path,
                             main_script_content)
                fhandler.write(main_script_content)
            os.chmod(main_script_path, 0o755)
            guest_main_script = os.path.join(guest_dir, main_script_name)

            # volume = os.path.abspath(tmpfiles['host_mpoint']) + ':' +
            # guest_dir
            # command = ['run', '-v', volume, image, '/bin/sh',
            #            guest_main_script]

            docker_client = docker.client.from_env()

            # Pull the image
            logging.info("[FACTS] docker pull '%s'", image)
            docker_client.images.pull(image)

            volumes = {os.path.abspath(tmpfiles['host_mpoint']): guest_dir}
            docker_client.containers.run(image=image,
                                         command=['/bin/sh',
                                                  guest_main_script],
                                         remove=True,
                                         stdout=True,
                                         volumes=volumes)

            facts_yaml = os.path.join(tmpfiles['host_mpoint'],
                                      'facts.yaml')
            try:
                with open(facts_yaml, 'r') as fhandler:
                    stdout = fhandler.read()
            except IOError:
                logging.info("[WARNING] The fact scripts "
                             "didn't write any fact in '%s'.",
                             facts_yaml)

        finally:
            for _, path in tmpfiles.items():
                if os.path.isdir(path):
                    logging.info('[FACTS DELETE] Temporary '
                                 'dir deleted: %s%s', path, os.sep)
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    logging.info('[FACTS DELETE] Temporary '
                                 'file deleted: %s', path)
                    os.unlink(path)
                else:
                    logging.info("[FACTS WARNING] Temporary file wasn't "
                                 "found: %s", path)

        facts = yaml.load(stdout)

        if not facts:
            logging.info("[FACTS] ERROR: unable to gather facts.")
            sys.exit(1)

        logging.info('[FACTS] System facts gathered: %s', str(facts))

        return facts


def dockerfile_patch(dockerfile_dir, j2_template_path, fact_scripts_paths):
    """The command line interface."""
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
            logging.info('[FACTS] Jinja patch loaded:\n%s\n',
                         jinja_patch)
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

        logging.info('[MAIN] Gathering facts from the image: %s', image_name)
        facts[image_name] = docker_facter.gather_facts(image_name)

        # Creating the patch for this image
        template = Template(jinja_patch)
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
    parser.add_argument('path', type=str,
                        help="The path where the 'Dockerfile' is located.")
    parser.add_argument('-o', '--output', default=None,
                        help='Save the patched Dockerfile to a file')
    parser.add_argument('-d', '--debug', action="store_true",
                        default=False, help='Show debug information')
    return parser.parse_args()


def main():
    """The program starts here."""
    args = parse_args()

    if args.debug:
        debug_level = logging.INFO
    else:
        debug_level = logging.ERROR

    logging.basicConfig(level=debug_level,
                        format='%(asctime)s %(message)s')

    # optional module for colored logs
    try:
        import coloredlogs
        coloredlogs.install()
    except ModuleNotFoundError:
        pass

    # garbage collector
    def garbage_collector(signum, frame):
        """Garbage collection."""
        gc.collect()
        logging.debug("%s: Garbage collection done.", sys.argv[0])
        if signum == signal.SIGINT:
            sys.stderr.write("Interrupted.\n".format())
            sys.exit(1)
        else:
            sys.exit(0)

    signal.signal(signal.SIGINT, garbage_collector)
    signal.signal(signal.SIGTERM, garbage_collector)

    try:
        from pygments import highlight
        from pygments.lexers import DockerLexer
        from pygments.formatters import TerminalFormatter

        color_enabled = True if sys.stdout.isatty() else False
    except ModuleNotFoundError:
        color_enabled = False

    # default facts gatherer
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    default_facts = os.path.join(script_dir, 'default-facts.sh')

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
        logging.info('[MAIN] The patched version of the Dockerfile:')
        logging.info('=============================================')

        if color_enabled:
            print(highlight(output, DockerLexer(), TerminalFormatter()))
        else:
            print(output)

    sys.exit(0)


if __name__ == '__main__':
    main()


# quicktest: python3 % test
# vim:ai:et:sw=4:ts=4:sts=4:tw=78:fenc=utf-8
