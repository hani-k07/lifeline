"""
utils/run.py - Cross-platform launcher for LIFELINE.
Replaces run.bat. Checks for environment, installs dependencies, and runs Streamlit.
"""

import os
import sys
import subprocess

def main():
    print("=== LIFELINE Cross-Platform Launcher ===")

    # 1. Check for .env file
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_file):
        print(f"[ERROR] Environment file not found at: {env_file}")
        print("Please copy '.env.example' to '.env' and configure your environment variables before running.")
        sys.exit(1)
    print("[INFO] Environment file (.env) found.")

    # 2. Run pip install -r requirements.txt
    req_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")
    if os.path.exists(req_file):
        print("[INFO] Installing/verifying dependencies from requirements.txt...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
            print("[INFO] Dependencies verified successfully.")
        except subprocess.CalledProcessError as e:
            print(f"[WARNING] Failed to verify all dependencies automatically: {e}")
            print("Please ensure your Python environment is active and run: pip install -r requirements.txt")
    else:
        print("[WARNING] requirements.txt not found. Skipping dependency check.")

    # 3. Launch streamlit run app.py
    app_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
    if not os.path.exists(app_file):
        print(f"[ERROR] Streamlit entry point app.py not found at: {app_file}")
        sys.exit(1)

    print("[INFO] Launching Streamlit application...")
    try:
        # Run streamlit as a module to make it robust and cross-platform
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_file])
    except KeyboardInterrupt:
        print("\n[INFO] LIFELINE shut down by user.")
    except Exception as e:
        print(f"[ERROR] Failed to start Streamlit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
