#!/usr/bin/env python3
"""
File Transfer Application
Desktop application that allows mobile devices to upload files wirelessly
"""

__version__ = "2.0.22"

import os
import sys
import socket
import threading
import subprocess
import json
import locale
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QTextEdit, QProgressBar, QMessageBox, QComboBox
from PyQt5.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtGui import QTextCursor
import qrcode
import io
import base64

if sys.platform == "win32":
    try:
        import wmi
    except ImportError:
        wmi = None


# Configuration
UPLOAD_FOLDER = 'uploaded'
DOWNLOAD_FOLDER = 'to_download'
# Allow all file extensions since we want to support images, videos, and various Apple formats
ALLOWED_EXTENSIONS = {''}  # Empty set means all extensions are allowed
MAX_CONTENT_LENGTH = None  # No file size limit to accommodate large video files
# Image extensions for download page
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'heic', 'heif'}

# Video extensions for download page
VIDEO_EXTENSIONS = {'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v'}

# Media extensions (images + videos) for download page
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)

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
pending_log_entries = []  # Entries waiting to be added to the log
current_language = 'zh'  # Default language
i18n_data = {}  # i18n data cache
SETTINGS_FILE = 'settings.json'  # Settings file for language preference

# Import for session management
from flask import session
import uuid


def load_i18n_data():
    """Load i18n data from JSON file"""
    global i18n_data
    try:
        with open('i18n.json', 'r', encoding='utf-8') as f:
            i18n_data = json.load(f)
    except Exception:
        i18n_data = {}


def get_text(key_path, lang=None):
    """Get translated text by key path (e.g., 'mobile_page.title')"""
    if lang is None:
        lang = current_language
    
    if not i18n_data:
        load_i18n_data()
    
    keys = key_path.split('.')
    try:
        result = i18n_data[lang]
        for key in keys:
            result = result[key]
        return result
    except (KeyError, TypeError):
        return key_path


def detect_system_language():
    """Detect system language and return 'zh' or 'en'"""
    try:
        system_lang = locale.getdefaultlocale()[0]
        if system_lang and system_lang.startswith('zh'):
            return 'zh'
        return 'en'
    except Exception:
        return 'zh'


def load_settings():
    """Load user settings from file"""
    global current_language
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                current_language = settings.get('language', detect_system_language())
        else:
            current_language = detect_system_language()
    except Exception:
        current_language = detect_system_language()


def save_settings():
    """Save user settings to file"""
    try:
        settings = {'language': current_language}
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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


def get_all_local_ips():
    """Get all local IP addresses from all network interfaces"""
    ips = []
    try:
        hostname = socket.gethostname()
        addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for addr in addresses:
            ip = addr[4][0]
            if ip not in ips and not ip.startswith('127.'):
                ips.append(ip)
    except Exception:
        pass
    
    if not ips:
        ips.append("127.0.0.1")
    
    return ips


def get_interface_name_by_ip(ip):
    """Get the actual network interface name for a given IP address"""
    if sys.platform == "win32" and wmi is not None:
        try:
            c = wmi.WMI()
            for interface in c.Win32_NetworkAdapterConfiguration():
                if interface.IPAddress:
                    for addr in interface.IPAddress:
                        if addr == ip and interface.NetConnectionID:
                            return interface.NetConnectionID
        except Exception:
            pass
    
    try:
        import psutil
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.address == ip:
                    interface_name = interface.replace('_', ' ')
                    if sys.platform == "darwin":
                        return interface_name
                    else:
                        return interface_name
    except Exception:
        pass
    
    return "Network Interface"


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
    return render_template('index.html', version=__version__)


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
    global pending_log_entries
    
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
    new_log_entries = []
    
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
                
                # Collect log entry for this file
                rel_path = os.path.join(file_info['device_folder'], file_info['filename'])
                new_log_entries.append(f"{rel_path} - UPLOADED ({file_info['size']} bytes)")
        
        # Update progress to 100% after successful upload
        upload_progress[session_id]['progress'] = 100
        upload_progress[session_id]['status'] = 'completed'
        upload_progress[session_id]['current_file'] = None
        
        # Add summary log entry
        success_count = len(uploaded_files)
        failed_count = len(files) - success_count
        new_log_entries.append(f"--- 上传结束: 成功 {success_count}, 失败 {failed_count}, 总数 {len(files)} ---")
        new_log_entries.append("")  # Blank line after summary
        
        # Add all new entries to pending log
        pending_log_entries.extend(new_log_entries)
        
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
        'upload_progress': upload_progress,
        'language': current_language
    })


@app.route('/i18n')
def get_i18n():
    """Get i18n translations for the current language"""
    if not i18n_data:
        load_i18n_data()
    
    return jsonify({
        'language': current_language,
        'translations': i18n_data.get(current_language, {})
    })


@app.route('/progress/<session_id>')
def get_progress(session_id):
    """Get upload progress for a specific session"""
    progress = upload_progress.get(session_id, {'progress': 0, 'status': 'not started'})
    return jsonify(progress)


@app.route('/download')
def download_page():
    """Serve the download page for mobile device"""
    # Create download folder if it doesn't exist
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    return render_template('download.html', version=__version__)


def is_media_file(filename):
    """Check if the file is an image or video"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in MEDIA_EXTENSIONS


@app.route('/download-list')
def get_download_list():
    """Get list of images to download"""
    images = []
    
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    else:
        try:
            # Get all files in download folder
            for filename in os.listdir(DOWNLOAD_FOLDER):
                file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(file_path) and is_media_file(filename):
                    images.append(filename)
            # Sort alphabetically
            images.sort()
        except Exception:
            pass
    
    return jsonify({
        'images': images,
        'total_count': len(images)
    })


@app.route('/download-image/<filename>')
def download_image(filename):
    """Serve the image file for download"""
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    try:
        return send_from_directory(DOWNLOAD_FOLDER, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404





class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orbit File Transfer")
        self.setWindowIcon(QIcon('icon.png'))  # Set the application icon
        self.setGeometry(100, 100, 600, 700)  # Reverted height since language selector no longer needs extra space
        
        # Load settings and i18n data
        load_settings()
        load_i18n_data()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title and language selector in a horizontal layout
        title_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel(f"Mobile File Transfer v{__version__}")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        # Add spacer to push language selector to the right
        title_layout.addStretch()
        
        # Language selector (smaller size)
        self.language_selector = QComboBox()
        self.language_selector.addItem(get_text('language_zh'), 'zh')
        self.language_selector.addItem(get_text('language_en'), 'en')
        self.language_selector.setCurrentIndex(0 if current_language == 'zh' else 1)
        self.language_selector.currentIndexChanged.connect(self.on_language_changed)
        self.language_selector.setFixedWidth(120)  # Set fixed width to make it smaller
        title_layout.addWidget(self.language_selector)
        
        layout.addLayout(title_layout)
        
        # Connection status
        self.status_label = QLabel("Status: Starting server...")
        layout.addWidget(self.status_label)
        
        # IP Address
        self.ip_label = QLabel("IP Address: Detecting...")
        layout.addWidget(self.ip_label)
        
        # Network interface selector
        self.interface_selector = QComboBox()
        self.interface_selector.currentIndexChanged.connect(self.on_interface_changed)
        layout.addWidget(self.interface_selector)
        
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
        
        # Open download folder button
        self.open_download_folder_button = QPushButton("Open Download Folder (to_download)")
        self.open_download_folder_button.clicked.connect(self.open_download_folder)
        layout.addWidget(self.open_download_folder_button)
        
        # Set up auto-refresh timer (every 2 seconds)
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.update_file_list)
        self.auto_refresh_timer.start(2000)  # Update every 2 seconds
        
        # Initialize
        self.update_file_list()
        self.populate_interface_selector()
        self.start_server()
        
        # Update UI with current language
        self.update_ui_language()
    
    def on_language_changed(self, index):
        """Handle language selection change"""
        global current_language
        if index >= 0:
            new_lang = self.language_selector.itemData(index)
            if new_lang != current_language:
                current_language = new_lang
                save_settings()
                self.update_ui_language()
    
    def update_ui_language(self):
        """Update UI text based on current language"""
        self.setWindowTitle(get_text('app_title'))
        self.status_label.setText(f"{get_text('server_status')}: {get_text('running')}")
        self.ip_label.setText(f"{get_text('ip_address')}: {current_ip or 'Detecting...'}")
        self.refresh_button.setText(get_text('refresh'))
        self.open_folder_button.setText(get_text('open_uploaded_folder'))
        self.open_download_folder_button.setText(get_text('open_download_folder'))
        
    def populate_interface_selector(self):
        """Populate the network interface selector with available IPs"""
        ips = get_all_local_ips()
        self.interface_selector.clear()
        for ip in ips:
            interface_name = get_interface_name_by_ip(ip)
            self.interface_selector.addItem(f"{ip} ({interface_name})", ip)
        
        if ips:
            self.interface_selector.setCurrentIndex(0)
    
    def on_interface_changed(self, index):
        """Handle interface selection change"""
        if index >= 0:
            new_ip = self.interface_selector.itemData(index)
            global current_ip
            current_ip = new_ip
            self.update_ui()
    
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
            self.ip_label.setText(f"{get_text('ip_address')}: {current_ip}:5000")
            
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
        """Update the list of uploaded files with improved logging"""
        global pending_log_entries
        
        # Keep the existing log
        existing_log = self.upload_log.toPlainText()
        
        # Collect all files from root and subdirectories
        all_files = []
        
        if os.path.exists(UPLOAD_FOLDER):
            for root, dirs, files in os.walk(UPLOAD_FOLDER):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    if os.path.isfile(filepath):
                        rel_path = os.path.relpath(filepath, UPLOAD_FOLDER)
                        size = os.path.getsize(filepath)
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                        all_files.append(f"{rel_path} ({size} bytes, {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
        
        # Process pending log entries
        if pending_log_entries:
            for entry in pending_log_entries:
                self.upload_log.append(entry)
            # Clear the pending entries
            pending_log_entries = []
        elif not existing_log and not all_files:
            # Initial state
            self.upload_log.setPlainText("No uploads yet...")
        
        # Update file list
        if all_files:
            self.file_list.setPlainText("\n".join(all_files))
        else:
            self.file_list.setPlainText("No files uploaded yet.")
            
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
    
    def open_download_folder(self):
        """Open the download folder in the system file explorer"""
        import subprocess
        import sys
        
        try:
            if sys.platform == "win32":
                # On Windows, use explorer to open the folder
                subprocess.run(["explorer", os.path.abspath(DOWNLOAD_FOLDER)])
            elif sys.platform == "darwin":  # macOS
                # On macOS, use open to open the folder
                subprocess.run(["open", os.path.abspath(DOWNLOAD_FOLDER)])
            else:  # Linux and other Unix-like systems
                # On Linux, use xdg-open to open the folder
                subprocess.run(["xdg-open", os.path.abspath(DOWNLOAD_FOLDER)])
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
        
        <div style="margin-top: 30px; text-align: center;">
            <a href="/download" style="color: #007bff; text-decoration: underline; font-size: 16px;">📥 从电脑上下载</a>
        </div>
    </div>

    <script>
        // i18n support
        let i18nData = {};
        let currentLanguage = 'zh';
        
        async function loadI18n() {
            try {
                const response = await fetch('/i18n');
                const data = await response.json();
                i18nData = data.translations;
                currentLanguage = data.language;
                updateUIText();
            } catch (error) {
                console.error('Error loading i18n:', error);
            }
        }
        
        function t(keyPath) {
            const keys = keyPath.split('.');
            let result = i18nData;
            for (const key of keys) {
                if (result && result[key]) {
                    result = result[key];
                } else {
                    return keyPath;
                }
            }
            return result;
        }
        
        function updateUIText() {
            document.title = t('mobile_page.title');
            document.querySelector('h1').textContent = '📱 ' + t('mobile_page.title');
            document.querySelector('#upload-btn').textContent = '📁 ' + t('mobile_page.select_upload');
            document.querySelector('#file-status-container h3').textContent = t('mobile_page.upload_status');
            document.querySelector('.file-list h3').textContent = t('mobile_page.uploaded_files');
            document.querySelector('a[href="/download"]').textContent = '📥 ' + t('mobile_page.download_from_pc');
        }
        
        // Check connection status
        async function checkConnection() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                const statusDiv = document.getElementById('connection-status');
                if (data.connected) {
                    statusDiv.className = 'status connected';
                    statusDiv.textContent = t('mobile_page.connected') + ' ' + data.ip_address;
                } else {
                    statusDiv.className = 'status disconnected';
                    statusDiv.textContent = t('mobile_page.disconnected');
                }
                
                // Update file list
                updateFileList(data.files);
                
                return data.connected;
            } catch (error) {
                console.error('Connection error:', error);
                const statusDiv = document.getElementById('connection-status');
                statusDiv.className = 'status disconnected';
                statusDiv.textContent = t('mobile_page.error_connecting');
                return false;
            }
        }

        function updateFileList(files) {
            const fileListContent = document.getElementById('file-list-content');
            
            if (files.length === 0) {
                fileListContent.innerHTML = t('mobile_page.no_files_uploaded');
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
                alert(t('mobile_page.select_at_least_one'));
                return;
            }

            // Disable upload button and show file status
            const uploadBtn = document.getElementById('upload-btn');
            uploadBtn.disabled = true;
            uploadBtn.textContent = t('mobile_page.uploading');
            
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
                    <span class="file-status-indicator" id="indicator-${file.name.replace(/[^a-zA-Z0-9]/g, '_')}">⏳ ${t('mobile_page.uploading_indicator')}</span>
                `;
                fileStatusList.appendChild(fileItem);
            });

            // Show progress
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');
            progressFill.style.width = '0%';
            progressText.textContent = t('mobile_page.uploading');

            try {
                // Upload ALL files in ONE request
                const formData = new FormData();
                Array.from(files).forEach(file => {
                    formData.append('files', file);
                });
                
                const uploadResponse = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const result = await uploadResponse.json();
                
                // Final update after all files complete
                progressFill.style.width = '100%';
                progressText.textContent = '100% - ' + t('mobile_page.upload_complete');
                
                if (result.success) {
                    // Mark all files as uploaded
                    Array.from(files).forEach(file => {
                        const fileNameClean = file.name.replace(/[^a-zA-Z0-9]/g, '_');
                        const indicatorElement = document.getElementById(`indicator-${fileNameClean}`);
                        if (indicatorElement) {
                            indicatorElement.textContent = '✅ ' + t('mobile_page.uploaded_indicator');
                            indicatorElement.style.color = '#28a745';
                        }
                    });
                    
                    alert(t('mobile_page.upload_success') + ' ' + result.files.length + ' ' + t('mobile_page.files'));
                } else {
                    // Mark all files as failed
                    Array.from(files).forEach(file => {
                        const fileNameClean = file.name.replace(/[^a-zA-Z0-9]/g, '_');
                        const indicatorElement = document.getElementById(`indicator-${fileNameClean}`);
                        if (indicatorElement) {
                            indicatorElement.textContent = '❌ ' + t('mobile_page.failed_indicator');
                            indicatorElement.style.color = '#dc3545';
                        }
                    });
                    alert(t('mobile_page.upload_failed') + ': ' + result.error);
                }
                
                // Re-enable button
                uploadBtn.disabled = false;
                uploadBtn.textContent = '� ' + t('mobile_page.select_upload');
                
                // Reset form and refresh file list
                fileInput.value = '';
                setTimeout(() => {
                    checkConnection();
                    progressFill.style.width = '0%';
                    progressText.textContent = '0%';
                }, 1000);
                
            } catch (error) {
                // Mark all files as failed
                Array.from(files).forEach(file => {
                    const fileNameClean = file.name.replace(/[^a-zA-Z0-9]/g, '_');
                    const indicatorElement = document.getElementById(`indicator-${fileNameClean}`);
                    if (indicatorElement) {
                        indicatorElement.textContent = '❌ ' + t('mobile_page.failed_indicator');
                        indicatorElement.style.color = '#dc3545';
                    }
                });
                
                // Re-enable button on error
                uploadBtn.disabled = false;
                uploadBtn.textContent = '� ' + t('mobile_page.select_upload');
                console.error('Upload error:', error);
                alert(t('mobile_page.upload_failed') + ': ' + error.message);
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
            // Load i18n first
            loadI18n();
            
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
    
    # Download interface
    download_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, maximum-scale=1.0, minimum-scale=1.0">
    <title>Orbit File Transfer - 下载</title>
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
            margin-top: 0;
        }
        .back-link {
            display: block;
            text-align: center;
            color: #007bff;
            text-decoration: underline;
            font-size: 16px;
            margin-bottom: 20px;
        }
        .gallery {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .image-item {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .image-item img,
        .image-item video {
            width: 100%;
            height: auto;
            border-radius: 6px;
            display: block;
        }
        .image-name {
            text-align: center;
            margin-top: 10px;
            font-size: 14px;
            color: #333;
            word-break: break-all;
        }
        .empty-message {
            text-align: center;
            color: #666;
            font-size: 16px;
            padding: 30px;
        }
        .hint {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📥 从电脑上下载</h1>
        <a href="/" class="back-link">← 返回上传页面</a>
        <p class="hint">提示：长按图片可以保存到相册</p>
        
        <div id="gallery" class="gallery">
            <div class="empty-message">加载中...</div>
        </div>
    </div>

    <script>
        // i18n support
        let i18nData = {};
        let currentLanguage = 'zh';
        
        async function loadI18n() {
            try {
                const response = await fetch('/i18n');
                const data = await response.json();
                i18nData = data.translations;
                currentLanguage = data.language;
                updateUIText();
            } catch (error) {
                console.error('Error loading i18n:', error);
            }
        }
        
        function t(keyPath) {
            const keys = keyPath.split('.');
            let result = i18nData;
            for (const key of keys) {
                if (result && result[key]) {
                    result = result[key];
                } else {
                    return keyPath;
                }
            }
            return result;
        }
        
        function updateUIText() {
            document.title = t('download_page.title');
            document.querySelector('h1').textContent = '📥 ' + t('download_page.title');
            document.querySelector('.back-link').textContent = '← ' + t('download_page.back_to_upload');
            document.querySelector('.hint').textContent = t('download_page.hint');
        }
        
        async function loadImages() {
            try {
                const response = await fetch('/download-list');
                const data = await response.json();
                
                const gallery = document.getElementById('gallery');
                
                if (data.images && data.images.length > 0) {
                    let html = '';
                    data.images.forEach(image => {
                        const isVideo = image.match(/\.(mp4|mkv|avi|mov|wmv|flv|webm|m4v)$/i);
                        if (isVideo) {
                            html += `
                                <div class="image-item">
                                    <video controls>
                                        <source src="/download-image/${encodeURIComponent(image)}" type="video/mp4">
                                        Your browser does not support the video tag.
                                    </video>
                                    <div class="image-name">${image}</div>
                                </div>
                            `;
                        } else {
                            html += `
                                <div class="image-item">
                                    <img src="/download-image/${encodeURIComponent(image)}" alt="${image}">
                                    <div class="image-name">${image}</div>
                                </div>
                            `;
                        }
                    });
                    gallery.innerHTML = html;
                } else {
                    gallery.innerHTML = `
                        <div class="empty-message">
                            <p>${t('download_page.no_images')}</p>
                            <p>${t('download_page.no_images_hint')}</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading images:', error);
                document.getElementById('gallery').innerHTML = `
                    <div class="empty-message">${t('download_page.load_failed')}</div>
                `;
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            loadI18n();
            loadImages();
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
    
    # Write download template
    with open(os.path.join(template_dir, 'download.html'), 'w', encoding='utf-8') as f:
        f.write(download_html)


def main():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    if not os.path.exists(DOWNLOAD_FOLDER):
        os.makedirs(DOWNLOAD_FOLDER)
    
    # Load settings and i18n data before creating templates
    load_settings()
    load_i18n_data()
    
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