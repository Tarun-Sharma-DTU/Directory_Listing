#!/bin/sh
# Exit on any error
set -e

# Make database migrations
python manage.py makemigrations --noinput

# Run database migrations
python manage.py migrate --noinput

# Collect static files

# Collect static files
python manage.py collectstatic --noinput

# Start the main process
exec "$@"
