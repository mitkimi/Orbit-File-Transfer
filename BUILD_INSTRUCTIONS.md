# Orbit File Transfer - Build Instructions

## Local Build

To build the Orbit File Transfer application locally, you can use the provided build scripts.

### Prerequisites

- Python 3.7 or higher
- Pip package manager

### Build Steps

#### Windows:
1. Double-click `build.bat` to run the build process, or
2. Open command prompt and run:
   ```
   python build_app.py
   ```

#### Linux/macOS:
1. Open terminal and run:
   ```
   chmod +x build.sh
   ./build.sh
   ```
   
   Or run directly:
   ```
   python3 build_app.py
   ```

### Cleaning Build Artifacts

To remove build artifacts (build/, dist/ folders and .spec files):

```
python build_app.py clean
```

### Manual Build

Alternatively, you can build manually using PyInstaller:

```
pip install pyinstaller
pyinstaller --onefile --windowed --name="Orbit File Transfer" --add-data="templates;templates" --icon=icon.ico main.py
```

### Output

After successful build:
- The executable will be located in the `dist/` folder
- A `distribution/` folder will be created with the executable and supporting files
- The application will be named "Orbit File Transfer" with the proper icon