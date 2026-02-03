#!/bin/bash

# Build script for creating a DEB package for Orbit File Transfer
# This script creates a Debian package for easy installation on Ubuntu/Debian systems

set -e  # Exit on any error

echo "Building DEB package for Orbit File Transfer..."

# Check if running on a Debian-based system
if ! command -v dpkg-deb &> /dev/null; then
    echo "Error: dpkg-deb is not available. This script only works on Debian-based systems."
    echo "Please install the 'dpkg-dev' package: sudo apt-get install dpkg-dev"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Activate virtual environment if it exists, otherwise install PyInstaller to system
if [ -d "orbit_env" ]; then
    echo "Activating virtual environment..."
    source orbit_env/bin/activate
else
    echo "Virtual environment not found, checking for PyInstaller..."
    if ! python3 -c "import PyInstaller" &> /dev/null; then
        echo "Error: PyInstaller is not installed. Please install it manually."
        exit 1
    fi
fi

# Check if PyInstaller is available
if ! python3 -c "import PyInstaller" &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install --break-system-packages pyinstaller || pip3 install pyinstaller
fi

# Version information
VERSION="1.0.0"
PACKAGE_NAME="orbit-file-transfer"
MAINTAINER="Orbit Developer <developer@example.com>"
DESCRIPTION="Wireless file transfer application allowing mobile devices to upload files to desktop"

echo "Creating temporary build directory..."
BUILD_DIR=$(mktemp -d)
echo "Build directory: $BUILD_DIR"

# Create the DEBIAN control directory structure
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/local/bin"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$BUILD_DIR/var/lib/orbit-file-transfer/templates"

# Create control file
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3, python3-flask, python3-pyqt5, python3-qrcode, python3-pil
Maintainer: $MAINTAINER
Description: $DESCRIPTION
 This application allows wireless file transfer from mobile devices to desktop computers.
 Users can connect to the desktop application via WiFi and upload files directly.
EOF

# Build the application executable
echo "Building application executable..."
pyinstaller --onefile \
    --name="orbit-file-transfer" \
    --add-data="templates:templates" \
    --clean \
    main.py

# Copy the built executable to the package
cp "dist/orbit-file-transfer" "$BUILD_DIR/usr/local/bin/"

# Make the executable accessible
chmod +x "$BUILD_DIR/usr/local/bin/orbit-file-transfer"

# Copy the icon
cp "icon.png" "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/orbit-file-transfer.png"

# Create desktop entry
cat > "$BUILD_DIR/usr/share/applications/orbit-file-transfer.desktop" << EOF
[Desktop Entry]
Name=Orbit File Transfer
Comment=Wireless file transfer from mobile devices
Exec=/usr/local/bin/orbit-file-transfer
Icon=/usr/share/icons/hicolor/256x256/apps/orbit-file-transfer.png
Terminal=false
Type=Application
Categories=Network;
EOF

# Copy templates
cp -r templates/* "$BUILD_DIR/var/lib/orbit-file-transfer/templates/"

# Create postinst script (ran after installation)
cat > "$BUILD_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
# Post-installation script
set -e

# Create symlink to make it available in PATH
ln -sf /usr/local/bin/orbit-file-transfer /usr/bin/orbit-file-transfer 2>/dev/null || true

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi

echo "Orbit File Transfer has been installed successfully!"
echo "You can start it from the applications menu or by running 'orbit-file-transfer' in terminal."

exit 0
EOF

# Create prerm script (ran before removal)
cat > "$BUILD_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
# Pre-removal script
set -e

# Remove symlink if it exists
rm -f /usr/bin/orbit-file-transfer 2>/dev/null || true

exit 0
EOF

# Create postrm script (ran after removal)
cat > "$BUILD_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/bash
# Post-removal script
set -e

# Update desktop database after removal
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi

exit 0
EOF

# Make scripts executable
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/DEBIAN/prerm"
chmod 755 "$BUILD_DIR/DEBIAN/postrm"

# Build the DEB package
echo "Building DEB package..."
OUTPUT_DEB="orbit-file-transfer_${VERSION}_amd64.deb"
dpkg-deb --build "$BUILD_DIR" "$OUTPUT_DEB"

# Clean up
rm -rf "$BUILD_DIR"

echo ""
echo "DEB package built successfully: $OUTPUT_DEB"
echo ""
echo "To install the package, run:"
echo "  sudo dpkg -i $OUTPUT_DEB"
echo "or"
echo "  sudo apt install ./$OUTPUT_DEB"
echo ""
echo "After installation, you can run the application from:"
echo "- The applications menu"
echo "- Command line: orbit-file-transfer"
echo ""

# Install the package if requested
if [[ "$1" == "--install" ]]; then
    echo "Installing the package..."
    sudo apt install ./"$OUTPUT_DEB"
fi