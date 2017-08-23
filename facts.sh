#!/bin/sh
#
# facts: gather system facts (like osfamily).
#
# Author: Asher256 <asher256@gmail.com>
# Website: http://www.asher256.com/
# License: GPL
#
# This source code follows the Google style guide for shell scripts:
# https://google.github.io/styleguide/shell.xml
#

set -u
set -e

lower_case() {
    echo "$1" | sed "y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklmnopqrstuvwxyz/"
}

uname=`uname`

# facts
osfamily=unknown
operatingsystem=`lower_case "$uname"`
kernelrelease=`uname -r`
architecture=`uname -m`

operatingsystem=`uname`
if [ "$operatingsystem" = "Linux" ]; then
  if [ -f /etc/alpine-release ]; then
    osfamily='alpine'
  elif [ -f /etc/debian_version ]; then
    osfamily='debian'
  elif [ -f /etc/redhat-release ]; then
    osfamily='redhat'
  elif [ -f /etc/SuSE-release ]; then
    osfamily='suse'
  elif [ -f /etc/arch-release ]; then
    osfamily='archlinux'
  fi
fi

# the last variable
echo "osfamily: $osfamily"
echo "operatingsystem: $osfamily"
echo "kernelrelease: $kernelrelease"
echo "architecture: $architecture"

# vim:ai:et:sw=2:ts=2:sts=2:tw=0:fenc=utf-8
