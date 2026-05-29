@echo off
setlocal EnableDelayedExpansion
:: =============================================================================
:: PDF RAG Analyzer - Start Script (Windows)
:: =============================================================================

title PDF RAG Analyzer - Start

echo.
echo ========================================================
echo    PDF RAG Analyzer  --  Start Script
echo ========================================================
echo.

:: ── Parse arguments ──────────────────────────────────────────────────────────
set BUILD_FLAG=
set DETACH_FLAG=-d

:parse_args
if "%~1"=="" goto :check_prereqs
if /i "%~1"=="--build"      set BUILD_FLAG=--build & shift & goto :parse_args
if /i "%~1"=="-b"           set BUILD_FLAG=--build & shift & goto :parse_args
if /i "%~1"=="--foreground" set DETACH_FLAG=        & shift & goto :parse_args
if /i "%~1"=="--help"       goto :show_help
if /i "%~1"=="-h"           goto :show_help
shift
goto :parse_args

:show_help
echo Usage: start.bat [options]
echo.
echo Options:
echo   --build, -b      Force rebuild of Docker images
echo   --foreground     Run in foreground (no -d flag)
echo   --help, -h       Show this help
exit /b 0

:: =============================================================================
:: 1. Check prerequisites
:: =============================================================================
:check_prereqs
echo [>>] Checking prerequisites
echo.

:: Check Docker
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERR]  Docker not found.
    echo        Install it from: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('docker --version 2^>^&1') do echo [ OK ]  %%v

:: Check Docker Compose (plugin v2 preferred, fallback to v1)
docker compose version >nul 2>&1
if not errorlevel 1 (
    set COMPOSE_CMD=docker compose
    for /f "tokens=*" %%v in ('docker compose version 2^>^&1') do echo [ OK ]  %%v
    goto :check_daemon
)
where docker-compose >nul 2>&1
if not errorlevel 1 (
    set COMPOSE_CMD=docker-compose
    for /f "tokens=*" %%v in ('docker-compose --version 2^>^&1') do echo [ OK ]  %%v
    goto :check_daemon
)
echo [ERR]  Docker Compose not found.
echo        Install it from: https://docs.docker.com/compose/install/
pause
exit /b 1

:check_daemon
:: Check Docker daemon
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERR]  Docker daemon is not running.
    echo        Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo [ OK ]  Docker daemon is running

:: =============================================================================
:: 2. Check available memory (informational)
:: =============================================================================
echo.
echo [>>] Checking system resources
echo.

for /f "skip=1 tokens=2" %%m in ('wmic OS get TotalVisibleMemorySize /value 2^>nul ^| findstr "="') do (
    set /a TOTAL_MB=%%m/1024
    echo [INFO]  Total RAM: !TOTAL_MB! MB
    if !TOTAL_MB! LSS 7168 (
        echo [WARN]  Less than 7 GB RAM detected -- Milvus may be unstable ^(8 GB+ recommended^)
    )
)

:: =============================================================================
:: 3. Environment file setup
:: =============================================================================
echo.
echo [>>] Checking environment configuration
echo.

set ENV_FILE=%~dp0backend\.env
set ENV_EXAMPLE=%~dp0backend\.env.example

if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        echo [WARN]  backend\.env not found -- copying from .env.example
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo [WARN]  Please edit backend\.env ^(set API keys, model names, etc.^) then re-run.
        echo.
        echo         notepad "%ENV_FILE%"
        echo.
    ) else (
        echo [ERR]  Neither backend\.env nor backend\.env.example found.
        echo        Create backend\.env before starting.
        pause
        exit /b 1
    )
) else (
    echo [ OK ]  backend\.env found
)

:: Frontend .env (optional)
if not exist "%~dp0frontend\.env" (
    if exist "%~dp0frontend\.env.example" (
        copy "%~dp0frontend\.env.example" "%~dp0frontend\.env" >nul
        echo [ OK ]  frontend\.env created from .env.example
    )
) else (
    echo [ OK ]  frontend\.env found
)

:: =============================================================================
:: 4. Verify docker-compose.yml
:: =============================================================================
echo.
echo [>>] Verifying project files
echo.

if not exist "%~dp0docker-compose.yml" (
    echo [ERR]  docker-compose.yml not found.
    echo        Run this script from the project root directory.
    pause
    exit /b 1
)
echo [ OK ]  docker-compose.yml found

:: =============================================================================
:: 5. Start services
:: =============================================================================
echo.
echo [>>] Starting services
echo.
echo [INFO]  Command: %COMPOSE_CMD% up %DETACH_FLAG% %BUILD_FLAG%
echo.

%COMPOSE_CMD% up %DETACH_FLAG% %BUILD_FLAG%
if errorlevel 1 (
    echo.
    echo [ERR]  Failed to start services. Check the output above for details.
    echo.
    echo        Useful diagnostic commands:
    echo          %COMPOSE_CMD% logs          -- all service logs
    echo          %COMPOSE_CMD% logs backend  -- backend logs only
    echo          %COMPOSE_CMD% ps            -- container status
    pause
    exit /b 1
)

:: =============================================================================
:: 6. Wait for backend health (detached mode only)
:: =============================================================================
if "%DETACH_FLAG%"=="" goto :end

echo.
echo [>>] Waiting for backend to become ready
echo.

set MAX_WAIT=120
set ELAPSED=0
set READY=0

:wait_loop
if %ELAPSED% GEQ %MAX_WAIT% goto :wait_timeout
curl -sf http://localhost:8000/health >nul 2>&1
if not errorlevel 1 (
    set READY=1
    goto :wait_done
)
timeout /t 5 /nobreak >nul
set /a ELAPSED+=5
<nul set /p =.
goto :wait_loop

:wait_timeout
echo.
echo [WARN]  Backend did not respond within %MAX_WAIT%s -- it may still be initializing.
echo [WARN]  Run '%COMPOSE_CMD% logs -f backend' to monitor startup.
goto :show_status

:wait_done
echo.
echo [ OK ]  Backend is ready

:show_status
:: =============================================================================
:: 7. Summary
:: =============================================================================
echo.
echo [>>] Service status
echo.
%COMPOSE_CMD% ps
echo.
echo ========================================================
echo    Services started -- access URLs
echo ========================================================
echo    Frontend UI  :  http://localhost
echo    Backend API  :  http://localhost:8000
echo    API Docs     :  http://localhost:8000/docs
echo    Neo4j Browser:  http://localhost:7474
echo    MinIO Console:  http://localhost:9001
echo --------------------------------------------------------
echo    Stop  :  stop.bat
echo    Logs  :  docker compose logs -f
echo ========================================================
echo.

:end
endlocal