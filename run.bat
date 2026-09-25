@echo off
echo =======================================
echo  LIFELINE v6.0 — Blood Logistics
echo  Pure Python / SQLite Edition
echo =======================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo [2/3] Setting up database...
python setup_database.py

echo.
echo [3/3] Demo credentials:
echo   admin@lifeline.com             / lifeline123  (Super Admin)
echo   mayo@lifeline.com              / lifeline123  (Hospital Admin - Mayo)
echo   services@lifeline.com          / lifeline123  (Hospital Admin - Services)
echo   jinnah@lifeline.com            / lifeline123  (Hospital Admin - Jinnah)
echo   shaukat@lifeline.com           / lifeline123  (Hospital Admin - Shaukat Khanum)
echo   mayo.worker@lifeline.com       / lifeline123  (Staff - Mayo)
echo   mayo.worker2@lifeline.com      / lifeline123  (Staff - Mayo)
echo   services.worker@lifeline.com   / lifeline123  (Staff - Services)
echo   jinnah.worker@lifeline.com     / lifeline123  (Staff - Jinnah)
echo   shaukat.worker@lifeline.com    / lifeline123  (Staff - Shaukat Khanum)
echo   shaukat.worker2@lifeline.com   / lifeline123  (Staff - Shaukat Khanum)
echo.
echo [NOTE] Add your OpenRouter API key to .env before using AI features.
echo.
streamlit run app.py
pause
