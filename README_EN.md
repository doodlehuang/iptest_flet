# Network Status Detection Tool

English | [简体中文](README.md)

NOTE: The App only provides Simplified Chinese interface at the moment.

A cross-platform network status detection tool built with the Flet framework, providing a clean and intuitive graphical interface for monitoring network connectivity and IP information.

## Features

- Display domestic and international IP addresses with their geographical locations
- Network freedom assessment
- GitHub connection speed test
- Google region detection
- Academic institution network (CNKI) auto-login status check
- IP address display mode toggle (full/masked)
- One-click IP address copy
- Beautiful graphical user interface
- Cross-platform support (Windows, macOS, Linux)

## Requirements

- Python 3.7 or higher
- Dependencies (see requirements.txt)

## Installation

1. Clone or download this project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the following command to start the program:
```bash
python src/main.py
```

After launch, the program will automatically perform network status detection. You can:
- Click the "Refresh" button to re-check network status
- Use "Toggle IP Display Mode" to switch between full/masked IP display
- Click "Copy IP Address" to copy the current IP information to clipboard

## Technical Details

- Built with Flet framework for cross-platform GUI
- Efficient network detection using asynchronous HTTP requests
- Multiple IP query services for accurate geolocation information 