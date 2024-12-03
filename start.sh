#!/bin/sh

# Exit script on any error
set -e

# Apply database migrations
python manage.py makemigrations
python manage.py migrate

# Start the gunicorn server
gunicorn --bind :8000 --workers 2 line_bot.wsgi