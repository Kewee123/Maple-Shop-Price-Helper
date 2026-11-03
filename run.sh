#!/bin/sh
# Start the prototype with its own virtualenv.
set -e
cd "$(dirname "$0")"
exec .venv/bin/python -m shop_price_helper
