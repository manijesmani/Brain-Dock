#!/bin/sh
set -eu
# The image's template renderer requires this directory to exist and be
# writable before it starts; /tmp is an empty tmpfs on every container boot.
mkdir -p /tmp/conf.d
