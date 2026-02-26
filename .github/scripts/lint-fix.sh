#!/bin/bash

# Automatically fix lint issues for frontend and backend

set -euo pipefail

# Fix lint issues in frontend
echo "Fixing frontend lint issues..."
cd frontend
npx eslint . --fix

# Fix lint issues in backend (Python - use ruff)
echo "Fixing backend lint issues..."
cd ..
ruff check --fix backend/ ai/ camera/
ruff format backend/ ai/ camera/

echo "Lint issues have been fixed!"
