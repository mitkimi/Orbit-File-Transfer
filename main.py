#!/usr/bin/env python3
"""
File Transfer Application
Desktop application that allows mobile devices to upload files wirelessly
"""

import os
import sys
import socket
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QTextEdit, QProgressBar, QMessageBox
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtGui import QTextCursor
import qrcode
import io
import base64


# Configuration
UPLOAD_FOLDER = 'uploaded'
# Allow all file extensions since we want to support images, videos, and various Apple formats
ALLOWED_EXTENSIONS = {''}  # Empty set means all extensions are allowed
MAX_CONTENT_LENGTH = None  # No file size limit to accommodate large video files

# Device-specific upload subdirectories
import re


def allowed_file(filename):
    """Allow all file types since we want to support images, videos, and Apple formats"""
    return True

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if MAX_CONTENT_LENGTH is not None:
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
else:
    app.config['MAX_CONTENT_LENGTH'] = None

# Global variables
current_ip = None
transfer_status = {}
upload_progress = {}

# Import for session management
from flask import session
import uuid


def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class CommunicationThread(QObject):
    """Thread for handling Flask server communication"""
    update_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.app = app
        
    def run(self):
        global current_ip
        current_ip = get_local_ip()
        
        # Start the Flask server
        self.app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)


@app.route('/')
def index():
    """Serve the mobile device interface"""
    return render_template('index.html')


@app.route('/desktop')
def desktop_view():
    """Serve the desktop interface"""
    return render_template('desktop.html')


def get_device_folder(user_agent):
    """Generate a device-specific folder name based on user agent"""
    if not user_agent:
        return 'unknown_device'
    
    # Try to extract device info from user agent
    if 'iPhone' in user_agent or 'iPad' in user_agent:
        device_name = 'iPhone'
    elif 'Android' in user_agent:
        device_name = 'Android'
    elif 'Windows' in user_agent:
        device_name = 'Windows_PC'
    elif 'Macintosh' in user_agent or 'Mac OS X' in user_agent:
        device_name = 'Mac'
    else:
        device_name = 'Unknown_Device'
    
    # Sanitize the device name to be a valid folder name
    sanitized_device_name = re.sub(r'[^\w\-_.]', '_', device_name)
    device_folder = os.path.join(app.config['UPLOAD_FOLDER'], sanitized_device_name)
    
    # Create the folder if it doesn't exist
    os.makedirs(device_folder, exist_ok=True)
    
    return device_folder


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads from mobile device - one by one"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if len(files) == 0:
        return jsonify({'error': 'No files selected'}), 400
    
    # Get device-specific folder
    user_agent = request.headers.get('User-Agent', '')
    device_folder = get_device_folder(user_agent)
    
    # Create a unique session for this upload
    session_id = str(uuid.uuid4())
    upload_progress[session_id] = {'progress': 0, 'status': 'starting', 'total_files': len(files), 'uploaded_files': [], 'current_file': None}
    
    uploaded_files = []
    
    try:
        for idx, file in enumerate(files):
            if file and allowed_file(file.filename):
                # Update progress and current file info
                upload_progress[session_id]['progress'] = int((idx / len(files)) * 100)
                upload_progress[session_id]['status'] = f'Uploading file {idx+1} of {len(files)}: {secure_filename(file.filename)}'
                upload_progress[session_id]['current_file'] = secure_filename(file.filename)
                
                filename = secure_filename(file.filename)
                filepath = os.path.join(device_folder, filename)
                
                # Handle duplicate filenames
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    name, ext = os.path.splitext(original_filepath)
                    filepath = f"{os.path.join(device_folder, f'{name}_{counter}{ext}')}"
                    counter += 1
                
                # Save the file
                file.save(filepath)
                file_info = {
                    'filename': os.path.basename(filepath),
                    'size': os.path.getsize(filepath),
                    'device_folder': os.path.basename(device_folder),
                    'timestamp': datetime.now().isoformat()
                }
                uploaded_files.append(file_info)
                upload_progress[session_id]['uploaded_files'].append(file_info)
        
        # Update progress to 100% after successful upload
        upload_progress[session_id]['progress'] = 100
        upload_progress[session_id]['status'] = 'completed'
        upload_progress[session_id]['current_file'] = None
        
    except Exception as e:
        upload_progress[session_id]['progress'] = 0
        upload_progress[session_id]['status'] = f'error: {str(e)}'
        return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'device_folder': os.path.basename(device_folder),
        'message': f'{len(uploaded_files)} file(s) uploaded successfully to {os.path.basename(device_folder)}',
        'files': uploaded_files
    })


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/status')
def get_status():
    """Get current upload status"""
    files = []
    device_folders = []
    
    if os.path.exists(UPLOAD_FOLDER):
        for item in os.listdir(UPLOAD_FOLDER):
            item_path = os.path.join(UPLOAD_FOLDER, item)
            if os.path.isdir(item_path):
                # This is a device folder
                device_folders.append({
                    'name': item,
                    'files': []
                })
                
                # Get files in this device folder
                for filename in os.listdir(item_path):
                    file_path = os.path.join(item_path, filename)
                    if os.path.isfile(file_path):
                        device_folders[-1]['files'].append({
                            'name': filename,
                            'size': os.path.getsize(file_path),
                            'timestamp': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                            'device_folder': item
                        })
            elif os.path.isfile(item_path):
                # This is a file in the root uploaded folder
                files.append({
                    'name': item,
                    'size': os.path.getsize(item_path),
                    'timestamp': datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat(),
                    'device_folder': 'root'
                })
    
    return jsonify({
        'ip_address': current_ip,
        'connected': True,
        'files': files,
        'device_folders': device_folders,
        'total_files': sum(len(folder['files']) for folder in device_folders) + len(files),
        'upload_progress': upload_progress
    })


@app.route('/progress/<session_id>')
def get_progress(session_id):
    """Get upload progress for a specific session"""
    progress = upload_progress.get(session_id, {'progress': 0, 'status': 'not started'})
    return jsonify(progress)





class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orbit File Transfer toolkit")
        self.setWindowIcon(QIcon('icon.png'))  # Set the application icon
        self.setGeometry(100, 100, 600, 700)  # Increased height from 500 to 700
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title
        title_label = QLabel("Mobile File Transfer")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Connection status
        self.status_label = QLabel("Status: Starting server...")
        layout.addWidget(self.status_label)
        
        # IP Address
        self.ip_label = QLabel("IP Address: Detecting...")
        layout.addWidget(self.ip_label)
        
        # QR Code Display
        self.qr_label = QLabel("QR Code will appear here")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumHeight(200)
        layout.addWidget(self.qr_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Upload log - increased size as it's more important
        self.upload_log = QTextEdit()
        self.upload_log.setReadOnly(True)
        self.upload_log.setMinimumHeight(250)  # Increased minimum height
        layout.addWidget(self.upload_log)
        
        # File list - reduced relative importance
        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        self.file_list.setMaximumHeight(150)  # Limited height for file list
        layout.addWidget(self.file_list)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh File List")
        self.refresh_button.clicked.connect(self.update_file_list)
        layout.addWidget(self.refresh_button)
        
        # Open uploaded folder button
        self.open_folder_button = QPushButton("Open Uploaded Folder")
        self.open_folder_button.clicked.connect(self.open_uploaded_folder)
        layout.addWidget(self.open_folder_button)
        
        # Set up auto-refresh timer (every 2 seconds)
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.update_file_list)
        self.auto_refresh_timer.start(2000)  # Update every 2 seconds
        
        # Initialize
        self.update_file_list()
        self.start_server()
        
    def start_server(self):
        """Start the Flask server in a separate thread"""
        self.comm_thread = CommunicationThread()
        self.server_thread = threading.Thread(target=self.comm_thread.run)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Update UI with IP and QR code after a short delay
        QTimer.singleShot(2000, self.update_ui)
        
    def update_ui(self):
        """Update UI with IP address and QR code"""
        if current_ip:
            self.ip_label.setText(f"IP Address: {current_ip}:5000")
            
            # Generate QR code
            qr_data = f"http://{current_ip}:5000/"
            qr_img = qrcode.make(qr_data)
            
            # Convert to pixmap for display
            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            qr_pixmap = QPixmap()
            qr_pixmap.loadFromData(buffer.getvalue())
            
            # Scale the image to fit the label
            scaled_pixmap = qr_pixmap.scaled(200, 200, Qt.KeepAspectRatio)
            self.qr_label.setPixmap(scaled_pixmap)
            
            self.status_label.setText("Status: Server running - Ready for connections")
        else:
            self.status_label.setText("Status: Error getting IP address")
    
    def update_file_list(self):
        """Update the list of uploaded files"""
        # Keep the existing log and append new entries
        existing_log = self.upload_log.toPlainText()
        
        # Collect all files from root and subdirectories
        all_files = []
        new_entries = []
        
        if os.path.exists(UPLOAD_FOLDER):
            for root, dirs, files in os.walk(UPLOAD_FOLDER):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    if os.path.isfile(filepath):
                        rel_path = os.path.relpath(filepath, UPLOAD_FOLDER)
                        size = os.path.getsize(filepath)
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                        
                        # Check if this file is already in the log to avoid duplicates
                        entry_text = f"{rel_path} - UPLOADED ({size} bytes)"
                        if entry_text not in existing_log:
                            new_entries.append(entry_text)
                        
                        all_files.append(f"{rel_path} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # Update upload log with only new entries
        if new_entries:
            if existing_log:
                self.upload_log.append("")  # Add a blank line before new entries
            for entry in new_entries:
                self.upload_log.append(entry)
        elif not existing_log and all_files:
            # If no existing log but files exist, add all as new entries
            for file_path, size, mtime in [(f.split('(')[0].strip(), f.split('(')[1].split()[0], f.split(',')[-1].strip()) for f in all_files]:
                self.upload_log.append(f"{file_path} - UPLOADED ({size} bytes)")
        
        # Update file list
        if all_files:
            self.file_list.setPlainText("\n".join(all_files))
        else:
            self.file_list.setPlainText("No files uploaded yet.")
            if not existing_log:
                self.upload_log.setPlainText("No uploads yet...")
            
        # Scroll to bottom of log
        self.upload_log.moveCursor(QTextCursor.End)
    
    def open_uploaded_folder(self):
        """Open the uploaded folder in the system file explorer"""
        import subprocess
        import sys
        
        try:
            if sys.platform == "win32":
                # On Windows, use explorer to open the folder
                subprocess.run(["explorer", os.path.abspath(UPLOAD_FOLDER)])
            elif sys.platform == "darwin":  # macOS
                # On macOS, use open to open the folder
                subprocess.run(["open", os.path.abspath(UPLOAD_FOLDER)])
            else:  # Linux and other Unix-like systems
                # On Linux, use xdg-open to open the folder
                subprocess.run(["xdg-open", os.path.abspath(UPLOAD_FOLDER)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {str(e)}")


def create_templates():
    """Create HTML templates for the web interface"""
    template_dir = os.path.join(os.getcwd(), 'templates')
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # Mobile interface
    mobile_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, maximum-scale=1.0, minimum-scale=1.0">
    <title>Orbit File Transfer toolkit - Mobile</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            font-size: 24px;
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            font-weight: bold;
        }
        
        .connected {
            background-color: #d4edda;
            color: #155724;
        }
        
        .disconnected {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .upload-section {
            margin: 20px 0;
        }
        
        #upload-btn {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 20px 40px;  /* Increased padding for larger button */
            font-size: 20px;     /* Increased font size */
            border-radius: 10px; /* Increased border radius */
            cursor: pointer;
            display: inline-block;
            width: auto;
            min-height: 60px;    /* Minimum height for easier tapping */
        }
        
        #upload-btn:hover {
            background-color: #0056b3;
        }
        
        #upload-btn:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        
        .progress-container {
            margin: 20px 0;
            position: relative;
        }
        
        .progress-bar {
            width: 100%;
            height: 30px;       /* Increased height to accommodate text */
            background-color: #e0e0e0;
            border-radius: 15px; /* Increased border radius */
            overflow: hidden;
            position: relative;
            display: flex;
            align-items: center;
        }
        
        .progress-fill {
            height: 100%;
            background-color: #28a745;
            width: 0%;
            transition: width 0.3s ease;
            position: absolute;
            top: 0;
            left: 0;
        }
        
        #progress-text {
            position: absolute;
            width: 100%;
            text-align: center;
            font-weight: bold;
            font-size: 14px;
            color: #333;
            z-index: 2;
            pointer-events: none;
        }
        
        .file-list {
            margin-top: 20px;
            text-align: left;
        }
        
        .file-item {
            padding: 12px;      /* Increased padding */
            margin: 8px 0;      /* Increased margin */
            background-color: #f8f9fa;
            border-radius: 6px; /* Increased border radius */
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .file-name {
            flex-grow: 1;
            font-size: 16px;    /* Increased font size */
            word-break: break-all;
        }
        .file-size {
            font-size: 14px;    /* Increased font size */
            color: #6c757d;
            margin-right: 10px;
        }
        .file-status-indicator {
            font-weight: bold;
            min-width: 100px;   /* Increased width */
            text-align: right;
            font-size: 14px;    /* Increased font size */
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 Orbit File Transfer</h1>
        
        <div id="connection-status" class="status disconnected">
            Connecting...
        </div>
        
        <div class="upload-section">
            <input type="file" id="file-input" multiple accept="*" style="display: none;">
            <button id="upload-btn">📁 Select & Upload Files</button>
        </div>
        
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div id="progress-text">0%</div>
        </div>
        
        <div class="file-status" id="file-status-container">
            <h3>File Upload Status:</h3>
            <div id="file-status-list">No files selected yet.</div>
        </div>
        
        <div class="file-list">
            <h3>Uploaded Files:</h3>
            <div id="file-list-content">No files uploaded yet.</div>
        </div>
    </div>

    <script>
        // Check connection status
        async function checkConnection() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                const statusDiv = document.getElementById('connection-status');
                if (data.connected) {
                    statusDiv.className = 'status connected';
                    statusDiv.textContent = `Connected! Server: ${data.ip_address}`;
                } else {
                    statusDiv.className = 'status disconnected';
                    statusDiv.textContent = 'Disconnected from server';
                }
                
                // Update file list
                updateFileList(data.files);
                
                return data.connected;
            } catch (error) {
                console.error('Connection error:', error);
                const statusDiv = document.getElementById('connection-status');
                statusDiv.className = 'status disconnected';
                statusDiv.textContent = 'Error connecting to server';
                return false;
            }
        }

        function updateFileList(files) {
            const fileListContent = document.getElementById('file-list-content');
            
            if (files.length === 0) {
                fileListContent.innerHTML = 'No files uploaded yet.';
                return;
            }
            
            let html = '<ul>';
            files.forEach(file => {
                html += `<li class="file-item">${file.name} (${Math.round(file.size/1024)} KB)</li>`;
            });
            html += '</ul>';
            
            fileListContent.innerHTML = html;
        }

        async function uploadFiles() {
            const fileInput = document.getElementById('file-input');
            const files = fileInput.files;
            
            if (files.length === 0) {
                alert('Please select at least one file to upload.');
                return;
            }

            // Disable upload button and show file status
            const uploadBtn = document.getElementById('upload-btn');
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            
            // Display file statuses
            const fileStatusList = document.getElementById('file-status-list');
            fileStatusList.innerHTML = '';
            
            Array.from(files).forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-status-item';
                fileItem.id = `status-${file.name.replace(/[^a-zA-Z0-9]/g, '_')}`;
                fileItem.innerHTML = `
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">(${formatFileSize(file.size)})</span>
                    <span class="file-status-indicator" id="indicator-${file.name.replace(/[^a-zA-Z0-9]/g, '_')}">⏳ WAITING</span>
                `;
                fileStatusList.appendChild(fileItem);
            });

            // Show progress
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');
            progressFill.style.width = '0%';
            progressText.textContent = '0%';

            try {
                // Upload files in parallel with limited concurrency (3-5 channels)
                const maxConcurrency = Math.min(5, Math.max(3, files.length)); // Between 3-5 channels
                const uploadedFiles = [];
                let completedCount = 0;

                // Create a copy of files array to process
                const filesArray = Array.from(files);

                // Process files in chunks based on max concurrency
                for (let i = 0; i < filesArray.length; i += maxConcurrency) {
                    const chunk = filesArray.slice(i, i + maxConcurrency);
                    
                    // Upload all files in the current chunk in parallel
                    const chunkPromises = chunk.map(async (file) => {
                        const fileNameClean = file.name.replace(/[^a-zA-Z0-9]/g, '_');
                        const indicatorElement = document.getElementById(`indicator-${fileNameClean}`);
                        
                        if (indicatorElement) {
                            indicatorElement.textContent = '⏳ UPLOADING';
                            indicatorElement.style.color = '#ffc107';
                        }
                        
                        // Prepare form data for single file
                        const formData = new FormData();
                        formData.append('files', file);
                        
                        try {
                            const uploadResponse = await fetch('/upload', {
                                method: 'POST',
                                body: formData
                            });

                            const result = await uploadResponse.json();
                            
                            completedCount++;
                            const totalProgress = (completedCount / filesArray.length) * 100;
                            progressFill.style.width = `${totalProgress}%`;
                            progressText.textContent = `${Math.round(totalProgress)}% - ${completedCount}/${filesArray.length} files`;

                            if (result.success) {
                                // Mark file as uploaded
                                if (indicatorElement) {
                                    indicatorElement.textContent = '✅ UPLOADED';
                                    indicatorElement.style.color = '#28a745';
                                }
                                
                                uploadedFiles.push(...result.files);
                                return result;
                            } else {
                                // Mark file as failed
                                if (indicatorElement) {
                                    indicatorElement.textContent = '❌ FAILED';
                                    indicatorElement.style.color = '#dc3545';
                                }
                                console.error(`Failed to upload ${file.name}:`, result.error);
                                return null;
                            }
                        } catch (error) {
                            completedCount++;
                            const totalProgress = (completedCount / filesArray.length) * 100;
                            progressFill.style.width = `${totalProgress}%`;
                            progressText.textContent = `${Math.round(totalProgress)}% - ${completedCount}/${filesArray.length} files`;
                            
                            // Mark file as failed
                            if (indicatorElement) {
                                indicatorElement.textContent = '❌ FAILED';
                                indicatorElement.style.color = '#dc3545';
                            }
                            console.error(`Upload error for ${file.name}:`, error);
                            return null;
                        }
                    });
                    
                    // Wait for all files in the current chunk to complete
                    await Promise.all(chunkPromises);
                }
                
                // Final update after all files complete
                progressFill.style.width = '100%';
                progressText.textContent = '100% - All files processed!';
                
                // Re-enable button
                uploadBtn.disabled = false;
                uploadBtn.textContent = '📷 Select & Upload Files';
                
                // Reset form and refresh file list
                fileInput.value = '';
                setTimeout(() => {
                    checkConnection();
                    progressFill.style.width = '0%';
                    progressText.textContent = '0%';
                }, 1000);
                
                alert(`Successfully uploaded ${uploadedFiles.length} file(s)!`);
            } catch (error) {
                // Re-enable button on error
                uploadBtn.disabled = false;
                uploadBtn.textContent = '📷 Select & Upload Files';
                console.error('Upload error:', error);
                alert('Upload failed: ' + error.message);
            }
        }
        
        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // Set up event listeners
        document.addEventListener('DOMContentLoaded', () => {
            // When upload button is clicked, trigger file input
            const uploadBtn = document.getElementById('upload-btn');
            const fileInput = document.getElementById('file-input');
            
            uploadBtn.addEventListener('click', function() {
                fileInput.click();
            });
            
            // When files are selected, automatically upload them
            fileInput.addEventListener('change', function(event) {
                if (event.target.files.length > 0) {
                    uploadFiles();
                }
            });
            
            // Check connection status every 5 seconds
            setInterval(checkConnection, 5000);
            
            // Initial connection check
            checkConnection();
        });
    </script>
</body>
</html>'''
    
    # Desktop interface
    desktop_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Transfer - Desktop</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .status-panel {
            background-color: #e9ecef;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }
        .file-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .file-card {
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            text-align: center;
            background: white;
        }
        .file-thumb {
            width: 100%;
            height: 100px;
            object-fit: cover;
            border-radius: 3px;
        }
        .file-name {
            font-size: 12px;
            word-break: break-word;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Desktop File Transfer Interface</h1>
        
        <div class="status-panel">
            <h3>Status Information</h3>
            <p><strong>Server Status:</strong> <span id="server-status">Running</span></p>
            <p><strong>IP Address:</strong> <span id="server-ip">Detecting...</span></p>
            <p><strong>Total Files:</strong> <span id="total-files">0</span></p>
        </div>
        
        <h3>Uploaded Files:</h3>
        <div id="file-grid" class="file-grid">
            <p>No files uploaded yet.</p>
        </div>
    </div>

    <script>
        async function loadStatus() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                document.getElementById('server-ip').textContent = data.ip_address || 'Unknown';
                document.getElementById('total-files').textContent = data.total_files;
                
                const fileGrid = document.getElementById('file-grid');
                if (data.files.length > 0) {
                    let html = '';
                    data.files.forEach(file => {
                        // Determine if it's an image file to show thumbnail
                        const isImage = /\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(file.name);
                        let thumbHtml = '';
                        
                        if (isImage) {
                            thumbHtml = `<img src="/uploads/${encodeURIComponent(file.name)}" alt="${file.name}" class="file-thumb">`;
                        } else {
                            thumbHtml = `<div style="height: 100px; display: flex; align-items: center; justify-content: center; background: #f8f9fa;">📄</div>`;
                        }
                        
                        html += `
                        <div class="file-card">
                            ${thumbHtml}
                            <div class="file-name">${file.name}</div>
                            <small>${Math.round(file.size/1024)} KB</small>
                        </div>`;
                    });
                    fileGrid.innerHTML = html;
                } else {
                    fileGrid.innerHTML = '<p>No files uploaded yet.</p>';
                }
            } catch (error) {
                console.error('Error loading status:', error);
            }
        }

        // Load status on page load and every 5 seconds
        document.addEventListener('DOMContentLoaded', () => {
            loadStatus();
            setInterval(loadStatus, 5000);
        });
    </script>
</body>
</html>'''
    
    # Write mobile template
    with open(os.path.join(template_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(mobile_html)
    
    # Write desktop template
    with open(os.path.join(template_dir, 'desktop.html'), 'w', encoding='utf-8') as f:
        f.write(desktop_html)


def main():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    create_templates()
    
    app_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False))
    app_thread.daemon = True
    app_thread.start()
    
    # Start desktop GUI
    app_gui = QApplication(sys.argv)
    app_gui.setWindowIcon(QIcon('icon.png'))  # Set icon for the entire application
    window = MainWindow()
    window.show()
    sys.exit(app_gui.exec_())


if __name__ == '__main__':
    main()