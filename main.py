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
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QTextEdit, QProgressBar
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QPixmap
import qrcode
import io
import base64


# Configuration
UPLOAD_FOLDER = 'uploaded'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

# Device-specific upload subdirectories
import re

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

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
    """Handle file uploads from mobile device"""
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
    upload_progress[session_id] = {'progress': 0, 'status': 'starting', 'total_files': len(files), 'uploaded_files': []}
    
    uploaded_files = []
    
    try:
        for idx, file in enumerate(files):
            if file and allowed_file(file.filename):
                # Update progress
                upload_progress[session_id]['progress'] = int((idx / len(files)) * 50)  # First 50% for processing
                upload_progress[session_id]['status'] = f'Processing file {idx+1} of {len(files)}'
                
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


def allowed_file(filename):
    """Check if the uploaded file is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Transfer App")
        self.setGeometry(100, 100, 600, 500)
        
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
        
        # File list
        self.file_list = QTextEdit()
        self.file_list.setReadOnly(True)
        layout.addWidget(self.file_list)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh File List")
        self.refresh_button.clicked.connect(self.update_file_list)
        layout.addWidget(self.refresh_button)
        
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
        if os.path.exists(UPLOAD_FOLDER):
            files = os.listdir(UPLOAD_FOLDER)
            file_info = []
            
            for filename in files:
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    file_info.append(f"{filename} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
            
            if file_info:
                self.file_list.setPlainText("\n".join(file_info))
            else:
                self.file_list.setPlainText("No files uploaded yet.")
        else:
            self.file_list.setPlainText("Upload folder does not exist.")


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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Transfer - Mobile</title>
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
        }
        .status {
            text-align: center;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
        }
        .connected {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .disconnected {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .upload-section {
            margin: 20px 0;
            text-align: center;
        }
        input[type="file"] {
            margin: 10px 0;
            width: 100%;
        }
        button {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .progress-container {
            margin: 20px 0;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background-color: #28a745;
            width: 0%;
            transition: width 0.3s;
        }
        .file-list {
            margin-top: 20px;
        }
        .file-item {
            padding: 10px;
            border-bottom: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 File Transfer</h1>
        
        <div id="connection-status" class="status disconnected">
            Connecting...
        </div>
        
        <div class="upload-section">
            <input type="file" id="file-input" multiple accept="image/*">
            <br>
            <button id="upload-btn">📤 Upload Files</button>
        </div>
        
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill"></div>
            </div>
            <div id="progress-text">0%</div>
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

            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }

            // Show progress
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');
            progressFill.style.width = '0%';
            progressText.textContent = '0%';

            try {
                // Note: Actual progress tracking would require more advanced implementation
                // For now, we'll simulate progress during upload
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                if (result.success) {
                    progressFill.style.width = '100%';
                    progressText.textContent = '100% - Upload Complete!';
                    
                    // Reset form and refresh file list
                    fileInput.value = '';
                    setTimeout(() => {
                        checkConnection();
                        progressFill.style.width = '0%';
                        progressText.textContent = '0%';
                    }, 1000);
                    
                    alert(`Successfully uploaded ${result.files.length} file(s)!`);
                } else {
                    alert('Upload failed: ' + result.message);
                }
            } catch (error) {
                console.error('Upload error:', error);
                alert('Upload failed: ' + error.message);
            }
        }

        // Set up event listeners
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('upload-btn').addEventListener('click', uploadFiles);
            
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
    window = MainWindow()
    window.show()
    sys.exit(app_gui.exec_())


if __name__ == '__main__':
    main()