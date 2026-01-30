#!/usr/bin/env python3
"""
Build script for Orbit File Transfer application
This script creates a standalone executable with proper icons and application name
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_application():
    """Build the Orbit File Transfer application executable"""
    
    print("Building Orbit File Transfer application...")
    
    # Check if required files exist
    required_files = ['main.py', 'icon.png', 'icon.ico']
    for file in required_files:
        if not os.path.exists(file):
            print(f"Error: Required file '{file}' not found!")
            return False
    
    # Check if templates directory exists
    if not os.path.exists('templates'):
        print("Error: Templates directory not found!")
        return False
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build command with proper parameters
    build_cmd = [
        "pyinstaller",
        "--onefile",           # Create a single executable file
        "--windowed",          # Don't show console (for GUI apps)
        "--name=Orbit File Transfer",  # Set the application name
        "--add-data=templates;templates",  # Include templates directory
        "--icon=icon.ico",     # Use the application icon
        "--clean",             # Clean cache before building
        "main.py"
    ]
    
    print("Executing build command:")
    print(" ".join(build_cmd))
    
    try:
        # Execute the build command
        result = subprocess.run(build_cmd, check=True)
        
        print("\nBuild completed successfully!")
        print(f"Executable location: {os.path.join('dist', 'Orbit File Transfer.exe' if sys.platform.startswith('win') else 'Orbit File Transfer')}")
        
        # Create a distribution folder with all necessary files
        dist_dir = "distribution"
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir)
        
        os.makedirs(dist_dir)
        
        # Copy the executable to distribution folder
        exe_name = "Orbit File Transfer.exe" if sys.platform.startswith('win') else "Orbit File Transfer"
        exe_path = os.path.join("dist", exe_name)
        
        if os.path.exists(exe_path):
            shutil.copy2(exe_path, os.path.join(dist_dir, exe_name))
        
        # Copy documentation and icons to distribution folder
        if os.path.exists("README.md"):
            shutil.copy2("README.md", dist_dir)
        
        if os.path.exists("icon.png"):
            shutil.copy2("icon.png", dist_dir)
        
        if os.path.exists("icon.ico"):
            shutil.copy2("icon.ico", dist_dir)
        
        print(f"Distribution package created in '{dist_dir}' folder")
        print("\nTo run the application, execute the generated executable file.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        return False
    except Exception as e:
        print(f"\nAn error occurred during build: {e}")
        return False

def clean_build_artifacts():
    """Remove build artifacts"""
    print("Cleaning build artifacts...")
    
    dirs_to_remove = ["build", "dist"]
    files_to_remove = [f for f in os.listdir(".") if f.endswith(".spec")]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed directory: {dir_name}")
    
    for file_name in files_to_remove:
        os.remove(file_name)
        print(f"Removed file: {file_name}")
    
    print("Clean completed!")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean_build_artifacts()
    else:
        success = build_application()
        if not success:
            print("\nBuild failed. Please check the error messages above.")
            sys.exit(1)