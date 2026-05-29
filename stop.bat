@echo off
setlocal EnableDelayedExpansion
:: =============================================================================
:: PDF RAG Analyzer - Stop Script (Windows)
:: =============================================================================

title PDF RAG Analyzer - Stop

echo.
echo ========================================================
echo    PDF RAG Analyzer  --  Stop Script
echo ========================================================
echo.

:: ── Parse arguments ──────────────────────────────────────────────────────────
set REMOVE_VOLUMES=0
set REMOVE_IMAGES=0

:parse_args
if "%~1"=="" goto :check_prereqs
if /i "%~1"=="--volumes" set REMOVE_VOLUMES=1 & shift & goto :parse_args
if /i "%~1"=="-v"        set REMOVE_VOLUMES=1 & shift & goto :parse_args
if /i "%~1"=="--images"  set REMOVE_IMAGES=1  & shift & goto :parse_args
if /i "%~1"=="-i"        set REMOVE_IMAGES=1  & shift & goto :parse_args
if /i "%~1"=="--all"     set REMOVE_VOLUMES=1 & set REMOVE_IMAGES=1 & shift & goto :parse_args
if /i "%~1"=="-a"        set REMOVE_VOLUMES=1 & set REMOVE_IMAGES=1 & shift & goto :parse_args
if /i "%~1"=="--help"    goto :show_help
if /i "%~1"=="-h"        goto :show_help
shift
goto :parse_args

:show_help
echo Usage: stop.bat [options]
echo.
echo Options:
echo   --volumes, -v    Also remove data volumes  (WARNING: data loss)
echo   --images,  -i    Also remove Docker images
echo   --all,     -a    Remove volumes + images   (full clean)
echo   --help,    -h    Show this help
exit /b 0

:: =============================================================================
:: 1. Check prerequisites
:: =============================================================================
:check_prereqs
echo [>>] Checking environment
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERR]  Docker not found.
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if not errorlevel 1 (
    set COMPOSE_CMD=docker compose
    goto :check_daemon
)
where docker-compose >nul 2>&1
if not errorlevel 1 (
    set COMPOSE_CMD=docker-compose
    goto :check_daemon
)
echo [ERR]  Docker Compose not found.
pause
exit /b 1

:check_daemon
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERR]  Docker daemon is not running. Start Docker Desktop first.
    pause
    exit /b 1
)
echo [ OK ]  Using: %COMPOSE_CMD%

if not exist "%~dp0docker-compose.yml" (
    echo [ERR]  docker-compose.yml not found. Run from the project root.
    pause
    exit /b 1
)

:: Warn about destructive flags
if %REMOVE_VOLUMES%==1 (
    echo.
    echo [WARN]  --volumes flag set -- ALL persistent data will be deleted!
)
if %REMOVE_IMAGES%==1 (
    echo [WARN]  --images flag set -- project Docker images will be removed.
)

:: =============================================================================
:: 2. Show current status
:: =============================================================================
echo.
echo [>>] Current container status
echo.
%COMPOSE_CMD% ps 2>nul || echo (no containers running)

:: =============================================================================
:: 3. Stop and remove containers
:: =============================================================================
echo.
echo [>>] Stopping all services
echo.

set DOWN_FLAGS=--remove-orphans
if %REMOVE_VOLUMES%==1 set DOWN_FLAGS=%DOWN_FLAGS% --volumes

echo [INFO]  Command: %COMPOSE_CMD% down %DOWN_FLAGS%
echo.

%COMPOSE_CMD% down %DOWN_FLAGS%
if errorlevel 1 (
    echo [WARN]  docker compose down reported an error -- attempting force stop...
    %COMPOSE_CMD% kill  2>nul
    %COMPOSE_CMD% rm -f 2>nul
    echo [ OK ]  Force stop completed
) else (
    echo [ OK ]  All containers stopped and removed
)

:: =============================================================================
:: 4. Optional: remove project images
:: =============================================================================
if %REMOVE_IMAGES%==0 goto :verify

echo.
echo [>>] Removing project Docker images
echo.

:: Derive project name from directory (lowercase, alphanumeric + dash)
for %%d in ("%~dp0.") do set PROJECT_RAW=%%~nxd
set PROJECT_NAME=%PROJECT_RAW%

for /f "tokens=*" %%i in ('docker images --filter "reference=%PROJECT_NAME%*" -q 2^>nul') do (
    docker rmi %%i 2>nul && echo [ OK ]  Removed image: %%i || echo [WARN]  Could not remove image: %%i
)

:: Also try compose-style names (projectname-service)
for %%s in (backend frontend) do (
    docker image inspect "%PROJECT_NAME%-%%s" >nul 2>&1
    if not errorlevel 1 (
        docker rmi "%PROJECT_NAME%-%%s" 2>nul && echo [ OK ]  Removed image: %PROJECT_NAME%-%%s
    )
)

:: =============================================================================
:: 5. Verify all project containers are gone
:: =============================================================================
:verify
echo.
echo [>>] Verifying shutdown
echo.

set REMAINING=
for /f "tokens=*" %%c in ('docker ps -a --filter "name=pdf-rag-" --format "{{.Names}}" 2^>nul') do (
    set REMAINING=%%c
)

if "!REMAINING!"=="" (
    echo [ OK ]  All pdf-rag-* containers have been removed
) else (
    echo [WARN]  The following containers are still present: !REMAINING!
    echo [WARN]  Force-remove with: docker rm -f !REMAINING!
)

:: =============================================================================
:: 6. Summary
:: =============================================================================
echo.
echo ========================================================
echo    All services stopped
if %REMOVE_VOLUMES%==1 echo    Data volumes removed ^(data has been deleted^)
if %REMOVE_IMAGES%==1  echo    Docker images removed
echo --------------------------------------------------------
echo    Restart :  start.bat
echo    Rebuild :  start.bat --build
echo ========================================================
echo.

endlocal