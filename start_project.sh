#!/bin/bash

echo "Starting Django backend..."

cd finance_backend
source ../env/bin/activate
python manage.py runserver 0.0.0.0:8000 &

cd ..

echo "Starting React frontend..."

cd ./frontend/stock-frontend
npm install
HOST=0.0.0.0 PORT=3000 npm start