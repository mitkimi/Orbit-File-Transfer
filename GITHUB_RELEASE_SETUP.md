# GitHub Auto Release Setup for Orbit File Transfer Toolkit

## Overview
This project now has automated release capabilities through GitHub Actions. When you push a tag in the format `v*` (e.g., `v1.0.0`), GitHub Actions will automatically create a release.

## How to Create a New Release

1. **Update your code** - Make sure all changes are committed to the main branch
2. **Create a tag** - Use semantic versioning format (vX.Y.Z):
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   ```
3. **Push the tag**:
   ```bash
   git push origin v1.0.0
   ```

## Available Workflows

1. **source-release.yml** - Creates a release with source code only
2. **build-binaries.yml** - Builds and releases executables for Windows, Linux, and macOS
3. **release.yml** - Basic release workflow with zipped source code
4. **build-release.yml** - Alternative build workflow

## Features

- Automated release creation when pushing tags
- Cross-platform builds (Windows, Linux, macOS)
- Pre-built executables for easy distribution
- Source code packaging for developers
- Automatic asset uploading to GitHub releases

## Requirements

Your project already has all necessary files:
- `requirements.txt` for dependencies
- `main.py` as the main application
- `templates/` directory for HTML files
- Icons (`icon.png`, `icon.ico`) for the application

## Customization

If you need to modify the build process, edit the workflow files in `.github/workflows/` directory. Each workflow handles different aspects of the release process.

## Troubleshooting

- If builds fail, check that all dependencies in `requirements.txt` are compatible with PyInstaller
- Make sure your `main.py` can run as a standalone script
- Ensure all necessary files are included in the PyInstaller build specification