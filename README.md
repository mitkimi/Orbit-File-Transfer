# File Transfer Application

A Python-based file transfer application that allows users to transfer images from mobile devices to a desktop computer via a local network connection.

## Features

- Desktop application with GUI showing connection status and file transfer progress
- QR code generation for easy mobile device connection
- Mobile-friendly web interface for file selection and upload
- Real-time progress tracking during file transfers
- Original quality preservation (no compression)
- No authentication required - works on local network
- Support for multiple image formats (JPG, PNG, GIF, BMP, TIFF, WEBP)

## Requirements

- Python 3.7+
- Windows, macOS, or Linux

## Installation

1. Clone or download this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:

```bash
python main.py
```

2. The desktop application will start and display:
   - Current IP address of the server
   - QR code for mobile device connection
   - Connection status
   - Uploaded files list

3. On your mobile device:
   - Scan the QR code displayed on the desktop application
   - Or manually navigate to the IP address shown (e.g., http://192.168.x.x:5000)
   - Select one or multiple image files to upload
   - Monitor the upload progress in real-time

4. Uploaded files will be stored in the `uploaded/` folder without any modifications.

## Project Structure

- `main.py`: Main application file containing both Flask server and PyQt5 GUI
- `templates/index.html`: Mobile web interface
- `templates/desktop.html`: Desktop web interface (accessible at /desktop)
- `uploaded/`: Folder where files are stored after upload
- `requirements.txt`: Python dependencies

## How It Works

1. The application starts a Flask web server on port 5000
2. A PyQt5 GUI displays connection status and QR code
3. Mobile users can connect via the QR code or IP address
4. Files are uploaded directly to the `uploaded/` folder
5. Progress tracking is handled via session-based status updates

## Security Note

This application is designed for local network use only and does not include authentication. Do not expose it to public networks without additional security measures.

## License

This project is open source and available under the MIT License.