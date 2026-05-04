@echo off
echo ===================================================
echo LIFELINE v3.0 - Initialization Script
echo ===================================================

echo [1/3] Checking and installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install requirements. Please check your Python installation.
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] Checking C++ DSA Engine...
if not exist "dsa_engine.exe" (
    echo dsa_engine.exe not found! Compiling C++ backend...
    if not exist "build" mkdir build
    cd build
    cmake ..
    if %errorlevel% neq 0 (
        echo CMake configuration failed. Do you have CMake installed?
        cd ..
        pause
        exit /b %errorlevel%
    )
    cmake --build . --config Release
    if %errorlevel% neq 0 (
        echo Compilation failed. Do you have a C++ compiler installed?
        cd ..
        pause
        exit /b %errorlevel%
    )
    copy Release\dsa_engine.exe ..\dsa_engine.exe
    cd ..
    echo C++ Engine successfully compiled.
) else (
    echo C++ DSA Engine already compiled.
)

echo.
echo [3/3] Launching LIFELINE Streamlit Application...
echo NOTE: Ensure your Supabase URL and Key are in the .env file!
echo.
python -m streamlit run app.py


pause
