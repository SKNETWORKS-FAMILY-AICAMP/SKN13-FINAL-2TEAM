@echo off
echo ========================================
echo    FastAPI Docker Management Script
echo ========================================
echo.

:menu
echo Choose an option:
echo 1. Build Docker image
echo 2. Run with docker-compose
echo 3. Stop containers
echo 4. Show logs
echo 5. Clean up everything
echo 6. Build and run (dev mode)
echo 7. Exit
echo.
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto build
if "%choice%"=="2" goto run
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto clean
if "%choice%"=="6" goto dev
if "%choice%"=="7" goto exit
echo Invalid choice. Please try again.
echo.
goto menu

:build
echo.
echo Building Docker image...
docker build -t fastapi-app .
echo.
echo Build completed!
pause
goto menu

:run
echo.
echo Starting containers...
docker-compose up -d
echo.
echo Containers started! Check http://localhost:8000
pause
goto menu

:stop
echo.
echo Stopping containers...
docker-compose down
echo.
echo Containers stopped!
pause
goto menu

:logs
echo.
echo Showing container logs (Ctrl+C to exit)...
docker-compose logs -f
goto menu

:clean
echo.
echo Cleaning up everything...
docker-compose down --rmi all --volumes --remove-orphans
docker system prune -f
echo.
echo Cleanup completed!
pause
goto menu

:dev
echo.
echo Building and running in development mode...
docker build -t fastapi-app .
docker-compose up -d
echo.
echo Application is starting...
echo Check logs with: docker-compose logs -f
echo Stop with: docker-compose down
echo.
pause
goto menu

:exit
echo.
echo Goodbye!
pause
exit
