#!/usr/bin/env bash

ENVFILE=github.env

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"
# set -a      # turn on automatic exporting
. "$ENVFILE"
# set +a      # turn off automatic exporting

if [ -z ${GITHUB_USER+x} ]; then
  echo "You need to set var GITHUB_USER in file ${ENVFILE}"
  exit
fi
if [ -z ${GITHUB_TOKEN+x} ]; then
  echo "You need to set var GITHUB_TOKEN in file ${ENVFILE}"
  exit
fi
echo GITHUB_USER = ${GITHUB_USER}

mkdir -p config
mkdir -p db

git clone --no-checkout https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/balarpan/miamap.git
cd miamap
# git config core.sparseCheckoutCone false
# git sparse-checkout disable
# git sparse-checkout set /restapi/
git sparse-checkout init --cone
git sparse-checkout set restapi
git checkout dev
git clean -fdx
git gc --prune=now

cd "$SCRIPT_DIR"
cp -rn ./miamap/restapi/config/* ./config/

CONFENV=./config/.env
if [ ! -f ${CONFENV} ]; then
  touch ${CONFENV}
  echo "# use 'openssl rand -hex 32' to generate strong key" >> ${CONFENV}
  echo "MIA__AUTH__SECRET_KEY=paste-your-secret-key-here" >> ${CONFENV}
fi
