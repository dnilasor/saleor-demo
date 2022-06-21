#!/usr/bin/env bash
set -e # exit on error

source variables/keys.sh


pip3 install -r requirements.txt

if [ "$RENDER_SERVICE_TYPE" = "web" ]; then
  python manage.py migrate --no-input
fi