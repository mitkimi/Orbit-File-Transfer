# File Transfer Application - Complete Summary

## Overview
This is a Python-based file transfer application that enables wireless transfer of images from mobile devices to a desktop computer via a local network connection. The application features both a desktop GUI and a mobile web interface.

## Key Features Implemented

### 1. Desktop Application with GUI
- PyQt5-based desktop application with connection status indicators
- Real-time display of connected IP address
- QR code generation for easy mobile device connection
- File listing and status monitoring
- Progress tracking for uploads

### 2. Mobile Web Interface
- Responsive design optimized for mobile devices
- Connection status indicators
- Single-button file selection and upload (clicking upload button triggers file picker)
- Real-time progress tracking during upload
- Uploaded files list display

### 3. Device-Specific Folder Organization
- Automatic detection of device type from user agent (Android, iPhone, Windows, Mac, etc.)
- Creation of device-specific folders in the `uploaded/` directory
- Files from different devices are stored in separate folders to prevent conflicts
- Proper sanitization of device names to create valid folder names

### 4. File Upload Functionality
- Multi-file selection and upload support
- Preservation of original file quality (no compression)
- Handling of duplicate filenames by appending counters
- Session-based progress tracking
- Error handling and reporting

### 5. Real-Time Status Updates
- Live connection status monitoring
- Progress tracking during uploads
- File listing with metadata (size, timestamp)
- Device folder display in desktop interface

## Technical Architecture

### Backend (Flask)
- RESTful API endpoints for file upload and status queries
- Session management for tracking upload progress
- Device detection and folder creation logic
- Secure file handling with filename sanitization

### Frontend (HTML/CSS/JavaScript)
- Mobile-optimized interface
- AJAX-based file uploads with progress tracking
- Real-time status updates via polling
- Responsive design for various screen sizes

### Desktop GUI (PyQt5)
- Cross-platform desktop application
- QR code display for mobile connection
- Connection status monitoring
- File listing and progress visualization

## Usage Instructions

1. Run the application with `python main.py`
2. The desktop application will start and display:
   - Local IP address (e.g., 192.168.5.120:5000)
   - QR code for mobile connection
   - Connection status
   - Uploaded files list

3. On mobile device:
   - Scan the QR code or navigate to the IP address
   - Click the "Select & Upload Files" button
   - Choose one or more image files
   - Monitor upload progress in real-time

4. Files will be organized in device-specific folders within the `uploaded/` directory

## Supported Formats
- JPG/JPEG
- PNG
- GIF
- BMP
- TIFF
- WEBP

## Security Considerations
- Designed for local network use only
- No authentication required (convenient for quick transfers)
- Files are stored in a designated upload folder
- Filename sanitization to prevent path traversal attacks

## Dependencies
- Flask
- PyQt5
- qrcode[pil]
- Pillow

## File Structure
- `main.py`: Main application (Flask server + PyQt5 GUI)
- `templates/index.html`: Mobile web interface
- `templates/desktop.html`: Desktop web interface
- `uploaded/`: Destination folder for uploaded files (with device subfolders)
- `requirements.txt`: Python dependencies
- `README.md`: Documentation

This application provides a seamless, user-friendly solution for transferring images from mobile devices to a desktop computer without requiring cloud services or complex setup procedures.