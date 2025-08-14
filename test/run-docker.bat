@echo off
echo FastAPI Docker Runner
echo ===================

echo.
echo Available commands:
echo 1. Build and start: docker-compose up --build
echo 2. Start only: docker-compose up
echo 3. Stop: docker-compose down
echo 4. View logs: docker-compose logs -f
echo 5. Rebuild: docker-compose build --no-cache
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo Building and starting the application...
    docker-compose up --build
) else if "%choice%"=="2" (
    echo Starting the application...
    docker-compose up
) else if "%choice%"=="3" (
    echo Stopping the application...
    docker-compose down
) else if "%choice%"=="4" (
    echo Viewing logs...
    docker-compose logs -f
) else if "%choice%"=="5" (
    echo Rebuilding the application...
    docker-compose build --no-cache
) else (
    echo Invalid choice. Please run the script again.
)

pause 