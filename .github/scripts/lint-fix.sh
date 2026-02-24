#!/bin/bash

# Automatically fix lint issues for frontend and backend

# Fix lint issues in frontend
echo "Fixing frontend lint issues..."
cd frontend
npm run lint -- --fix  # Assuming npm is used for frontend

# Fix lint issues in backend
echo "Fixing backend lint issues..."
cd ../backend
npm run lint -- --fix  # Assuming npm is used for backend

echo "Lint issues have been fixed!"