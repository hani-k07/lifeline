@echo off
echo =======================================
echo  LIFELINE v6.0 - Blood Logistics
echo  Pure Python / SQLite Edition
echo =======================================
echo.

if not exist .env (
    echo [setup] No .env found - copying .env.example. Edit it to add your OpenRouter key and set APP_ENV.
    copy .env.example .env >nul
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo [2/3] Preparing database (creates it on first run, migrates it afterwards)...
python -m scripts.setup_db

echo.
echo [3/3] Starting LIFELINE...
echo   Demo accounts are listed on the login page only when APP_ENV=demo in .env.
echo   AI features need OPENROUTER_API_KEY in .env; everything else works without it.
echo.
streamlit run app.py
pause
