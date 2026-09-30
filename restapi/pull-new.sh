#!/usr/bin/env bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"

cd miamap
git sparse-checkout reapply
git pull

cd "$SCRIPT_DIR"
cp -rn ./miamap/restapi/config/* ./config/

CONFENV=${SCRIPT_DIR%%/}/config/.env
if [ ! -f ${CONFENV} ]; then
  touch ${CONFENV}
  echo "# use 'openssl rand -hex 32' to generate strong key" >> ${CONFENV}
  echo "MIA__AUTH__SECRET_KEY=paste-your-secret-key-here" >> ${CONFENV}
  echo "NEWSFEED_USER=your-newsfeed-user" >> ${CONFENV}
  echo "NEWSFEED_PWD=your-newsfeed-pwd" >> ${CONFENV}
fi
