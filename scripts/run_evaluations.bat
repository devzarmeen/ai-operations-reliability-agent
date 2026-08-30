@echo off
echo ==============================================
echo Running Offline Dry-Run Evaluation...
echo ==============================================
cd %~dp0\..\backend
call poetry run python ../evaluation/run_evaluation.py
if %ERRORLEVEL% NEQ 0 (
    echo Offline evaluation failed!
    exit /b %ERRORLEVEL%
)

echo.
echo ==============================================
echo Running Live Integration Evaluation...
echo ==============================================
call poetry run python ../evaluation/run_live_evaluation.py
if %ERRORLEVEL% NEQ 0 (
    echo Live evaluation failed!
    exit /b %ERRORLEVEL%
)

echo.
echo All evaluations completed successfully!
pause
