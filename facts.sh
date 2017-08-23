#!/bin/sh
#
# facts: gather system facts (like osfamily).
#
# Author: Asher256 <asher256@gmail.com>
# Github repo: https://github.com/Asher256/docker-pbuild/
# License: GPL
#
# This source code follows the Google style guide for shell scripts:
# https://google.github.io/styleguide/shell.xml
#

set -u
set -e

# facts
osfamily=unknown
operatingsystem=`uname`
kernelrelease=`uname -r`
architecture=`uname -m`

if [ "$operatingsystem" = "Linux" ]; then
  if [ -f /etc/alpine-release ]; then
    osfamily='Alpine'
  elif [ -f /etc/debian_version ]; then
    osfamily='Debian'
  elif [ -f /etc/redhat-release ]; then
    osfamily='RedHat'
  elif [ -f /etc/SuSE-release ]; then
    osfamily='SuSE'
  elif [ -f /etc/arch-release ]; then
    osfamily='Archlinux'
  fi
fi

# Output in the Yaml format
{
  echo "osfamily: $osfamily"
  echo "operatingsystem: $operatingsystem"
  echo "kernelrelease: $kernelrelease"
  echo "architecture: $architecture"
} >> facts.yaml

exit 0

# vim:ai:et:sw=2:ts=2:sts=2:tw=0:fenc=utf-8
