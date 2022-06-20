#!/usr/bin/env bash
set -e # exit on error

source variables/keys.sh


pip3 install -r requirements.txt

python manage.py migrate --no-input