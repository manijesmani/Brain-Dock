#!/bin/sh
set -eu
umask 077
cat /etc/redis/redis.conf > /tmp/redis.conf
printf '\nrequirepass %s\n' "$(cat /run/secrets/redis_password)" >> /tmp/redis.conf
exec redis-server /tmp/redis.conf
