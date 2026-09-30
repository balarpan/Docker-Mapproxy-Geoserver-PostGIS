#!/usr/bin/env bash

ENVFILENAME=github.env

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ENVFILE="${SCRIPT_DIR%%/}/${ENVFILENAME}"
RED='\e[31m'
BLU='\e[34m'
GRN='\e[32m'
NC='\e[0m'  # No Color

if [ ! -f ${ENVFILE} ]; then
  echo "You must create ${ENVFILE} with params GITHUB_USER and GITHUB_TOKEN to use this script"
  exit 1
fi
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

CONFENV=${SCRIPT_DIR%%/}/config/.env
if [ ! -f ${CONFENV} ]; then
  touch ${CONFENV}
  echo "# use 'openssl rand -hex 32' to generate strong key" >> ${CONFENV}
  echo "MIA__AUTH__SECRET_KEY=paste-your-secret-key-here" >> ${CONFENV}
  echo "NEWSFEED_USER=your-newsfeed-user" >> ${CONFENV}
  echo "NEWSFEED_PWD=your-newsfeed-pwd" >> ${CONFENV}
else
  if ! grep -q '^MIA__AUTH__SECRET_KEY\s*=' "${CONFENV}"; then
    echo -e "You must set proper MIA__AUTH__SECRET_KEY in ${GRN}${CONFENV}${NC} file"
  fi
  if ! grep -q '^MIA__AUTH__NEWSFEED_USER\s*=' "${CONFENV}"; then
    echo -e "You must set proper MIA__AUTH__NEWSFEED_USER in ${GRN}${CONFENV}${NC} file"
  fi
  if ! grep -q '^MIA__AUTH__NEWSFEED_PWD\s*=' "${CONFENV}"; then
    echo -e "You must set proper MIA__AUTH__NEWSFEED_PWD in ${GRN}${CONFENV}${NC} file"
  fi
fi
