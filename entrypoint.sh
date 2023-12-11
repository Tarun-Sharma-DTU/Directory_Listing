#!/bin/sh
# Exit on any error
set -e

# Run database migrations
python manage.py migrate --noinput

# Start the main process
exec "$@"
