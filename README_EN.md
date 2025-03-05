# Network Status Detection Tool

English | [简体中文](README.md)

A cross-platform network status detection tool built with the Flet framework, providing a clean and intuitive graphical interface for monitoring network connectivity and IP information.

## Features

- Display domestic and international IP addresses with their geographical locations
- Network freedom assessment
- GitHub connection speed test
- Google region detection
- Academic institution network (CNKI) auto-login status check
- Streaming service unlock status detection (Netflix, YouTube Premium)
- IP address display mode toggle (full/masked)
- One-click IP address copy
- Multi-language support (Simplified Chinese, Traditional Chinese, English)
- Beautiful graphical user interface
- Cross-platform support (Windows, macOS, Linux)
- Built-in network safety reminder for restricted regions

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

After launch, you will need to:
1. Read and agree to the safety notice
2. Select your preferred interface language
3. Click "Continue" to enter the main interface

In the main interface, you can:
- View current network status information
- Click the "Refresh" button to re-check network status
- Use "Toggle Display Mode" to switch between full/masked IP display
- Click "Copy" to copy the current IP information to clipboard
- View streaming service unlock status (when network is unrestricted)

## Technical Details

- Built with Flet framework for cross-platform GUI
- Efficient network detection using asynchronous HTTP requests
- Multiple IP query services for accurate geolocation information
- Built-in network safety check mechanism 