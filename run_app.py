#!/usr/bin/env python3
"""
Launcher script for the AI Model Card Generator
This script provides options to run either the web interface or terminal version.
"""

import os
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def show_menu():
    """Show application options"""
    print("🏥 AI MODEL CARD GENERATOR")
    print("=" * 40)
    print("Choose how to run the application:")
    print()
    print("1. 🌐 Web Interface (Streamlit)")
    print("2. 💻 Terminal Interface")
    print("3. ❌ Exit")
    print()

def run_web_interface():
    """Run the Streamlit web interface"""
    print("🌐 Starting web interface...")
    print("   URL: http://localhost:5000")
    print("   Press Ctrl+C to stop")
    print()
    
    # Check if GEMINI_API_KEY is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  WARNING: GEMINI_API_KEY environment variable is not set!")
        print("   The application will fail without this API key.")
        print("   Set it with: export GEMINI_API_KEY='your_key_here'")
        print()
    
    # Launch Streamlit directly
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "src/core/app.py", 
        "--server.port", "5000",
        "--server.address", "localhost"
    ])

def run_terminal_interface():
    """Run the terminal interface"""
    print("💻 Starting terminal interface...")
    print()
    subprocess.run([sys.executable, "terminal_app.py"])

if __name__ == "__main__":
    while True:
        show_menu()
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            run_web_interface()
            break
        elif choice == "2":
            run_terminal_interface()
            break
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
            print()
