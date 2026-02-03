#!/bin/bash

# Build script for creating an RPM package for Orbit File Transfer
# This script creates an RPM package for easy installation on CentOS/RHEL/Fedora systems

set -e  # Exit on any error

echo "Building RPM package for Orbit File Transfer..."

# Check if running on a RPM-based system
if ! command -v rpmbuild &> /dev/null; then
    echo "Error: rpmbuild is not available. This script only works on RPM-based systems (CentOS/RHEL/Fedora)."
    echo "Please install the 'rpm-build' package: sudo yum install rpm-build or sudo dnf install rpm-build"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Activate virtual environment if it exists
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
RELEASE="1"
PACKAGE_NAME="orbit-file-transfer"
MAINTAINER="Orbit Developer <developer@example.com>"
DESCRIPTION="Wireless file transfer application allowing mobile devices to upload files to desktop"

echo "Creating temporary build directory..."
BUILD_DIR=$(mktemp -d)
echo "Build directory: $BUILD_DIR"

# Create RPM build directory structure
mkdir -p "$BUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Build the application executable
echo "Building application executable..."
pyinstaller --onefile \
    --name="orbit-file-transfer" \
    --add-data="templates:templates" \
    --clean \
    main.py

# Create the source tarball
echo "Creating source tarball..."
SOURCE_TARBALL="${PACKAGE_NAME}-${VERSION}.tar.gz"
tar -czf "$BUILD_DIR/SOURCES/$SOURCE_TARBALL" \
    --exclude="orbit_env" \
    --exclude="build" \
    --exclude="dist" \
    --exclude="*.spec" \
    --exclude="__pycache__" \
    --exclude=".git" \
    .

# Create the spec file
SPEC_FILE="$BUILD_DIR/SPECS/$PACKAGE_NAME.spec"
cat > "$SPEC_FILE" << EOF
Name:           $PACKAGE_NAME
Version:        $VERSION
Release:        $RELEASE%{?dist}
Summary:        Wireless file transfer application

License:        GPL
BuildArch:      noarch
Vendor:         Orbit Developer
URL:            https://example.com
Source0:        %{name}-%{version}.tar.gz

Requires:       python3, python3-flask, python3-pyqt5, python3-qrcode, python3-pillow
BuildRequires:  python3-devel

%description
$DESCRIPTION
This application allows wireless file transfer from mobile devices to desktop computers.
Users can connect to the desktop application via WiFi and upload files directly.

%prep
%setup -q

%build
# Nothing to build from source

%install
mkdir -p %{buildroot}/usr/local/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps
mkdir -p %{buildroot}/var/lib/orbit-file-transfer/templates

# Install the executable
cp dist/orbit-file-transfer %{buildroot}/usr/local/bin/orbit-file-transfer
chmod +x %{buildroot}/usr/local/bin/orbit-file-transfer

# Install the icon
cp icon.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/orbit-file-transfer.png

# Install desktop entry
cat > %{buildroot}/usr/share/applications/orbit-file-transfer.desktop << 'DESKTOP_EOF'
[Desktop Entry]
Name=Orbit File Transfer
Comment=Wireless file transfer from mobile devices
Exec=/usr/local/bin/orbit-file-transfer
Icon=/usr/share/icons/hicolor/256x256/apps/orbit-file-transfer.png
Terminal=false
Type=Application
Categories=Network;
DESKTOP_EOF

# Install templates
cp -r templates/* %{buildroot}/var/lib/orbit-file-transfer/templates/

%files
/usr/local/bin/orbit-file-transfer
/usr/share/applications/orbit-file-transfer.desktop
/usr/share/icons/hicolor/256x256/apps/orbit-file-transfer.png
/var/lib/orbit-file-transfer/templates/*

%pre
# Pre-installation script
echo "Preparing to install Orbit File Transfer..."

%post
# Post-installation script
# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi

echo "Orbit File Transfer has been installed successfully!"
echo "You can start it from the applications menu or by running 'orbit-file-transfer' in terminal."

%preun
# Pre-uninstallation script
echo "Uninstalling Orbit File Transfer..."

%postun
# Post-uninstallation script
# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi

%changelog
* $(date +"%a %b %d %Y") $MAINTAINER - $VERSION-$RELEASE
- Initial package
EOF

# Build the RPM package
echo "Building RPM package..."
rpmbuild --define "_topdir $BUILD_DIR" \
         --define "_tmppath /tmp" \
         -bb "$SPEC_FILE"

# Copy the resulting RPM to current directory
RPM_PATH=$(find "$BUILD_DIR/RPMS" -name "*.rpm" -type f | head -n 1)
if [ -n "$RPM_PATH" ]; then
    OUTPUT_RPM="$(basename "$RPM_PATH")"
    cp "$RPM_PATH" "$OUTPUT_RPM"
    echo ""
    echo "RPM package built successfully: $OUTPUT_RPM"
    echo ""
    echo "To install the package, run:"
    echo "  sudo yum install ./$OUTPUT_RPM"
    echo "or for newer versions of Fedora/CentOS Stream:"
    echo "  sudo dnf install ./$OUTPUT_RPM"
    echo ""
    echo "After installation, you can run the application from:"
    echo "- The applications menu"
    echo "- Command line: orbit-file-transfer"
    echo ""
else
    echo "Error: Failed to build RPM package"
    exit 1
fi

# Clean up
rm -rf "$BUILD_DIR"

# Install the package if requested
if [[ "$1" == "--install" ]]; then
    echo "Installing the package..."
    if command -v dnf &> /dev/null; then
        sudo dnf install ./"$OUTPUT_RPM"
    else
        sudo yum install ./"$OUTPUT_RPM"
    fi
fi