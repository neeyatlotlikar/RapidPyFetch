# RapidPyFetch

A lightweight Python download manager that integrates with aria2c daemon for reliable, high-performance downloads. Designed for browser extension integration via native messaging.

## Overview

RapidPyFetch provides a clean interface between browser extensions and the powerful aria2c download utility. Instead of managing downloads directly in Python, it leverages aria2c's robust built-in retry mechanisms and RPC interface for optimal reliability and performance.

## Architecture

- **aria2c daemon**: Handles actual downloads with built-in retry logic and resume capabilities
- **Python helper**: Processes single commands via native messaging and exits cleanly
- **Browser integration**: Communicates through native messaging protocol

### Design Philosophy

- **Simplicity over complexity**: No background monitoring threads or complex retry logic
- **Reliability**: Leverages aria2c's proven download capabilities
- **Efficiency**: One command per execution, no persistent processes
- **Observability**: Manual log checking preferred over automated monitoring

## Prerequisites

- Python 3.11+
- aria2c installed and accessible in PATH
- Ubuntu 24.04+ (tested environment)

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/neeyatlotlikar/RapidPyFetch.git
    cd RapidPyFetch
    ```

2. Create and activate virtual environment:

    ```bash
    python3 -m venv venv
    #or
    uv venv venv

    source venv/bin/activate
    ```

3. Install dependencies:

    ```bash
    pip install aria2p python-dotenv
    ```

4. Create `.env` file:

    ```bash
    cp .env.example .env
    # Edit .env with your configuration
    ```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
ARIA2_RPC_SECRET=your_secret_here
RPC_LISTEN_PORT=6800
ARIA2_RPC_HOSTNAME=http://localhost
LOG_PATH=/path/to/downloader.log
```

### aria2c Daemon Setup

Start aria2c daemon with recommended settings:

```bash
aria2c \
  --enable-rpc \
  --rpc-listen-port=6800 \
  --rpc-secret=your_secret_here \
  --rpc-allow-origin-all=false \
  --rpc-listen-all=false \
  --dir=/path/to/downloads \
  --continue=true \
  --max-tries=10 \
  --retry-wait=3 \
  --max-concurrent-downloads=10 \
  --max-connection-per-server=5 \
  --log=/path/to/aria2c.log \
  --log-level=info \
  -D
```

### Systemd Service (Optional)

Create `/etc/systemd/system/aria2c.service`:

```ini
[Unit]
Description=Aria2 Download Daemon
After=network-online.target

[Service]
Type=forking
User=your_user
ExecStart=/usr/bin/aria2c --enable-rpc --rpc-secret=your_secret_here --max-tries=10 --retry-wait=3 --continue=true --log=/var/log/aria2c.log -D

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable aria2c
sudo systemctl start aria2c
```

## Usage

### Supported Commands

The helper processes JSON commands via stdin:

#### Add Download

```json
{
    "command": "add",
    "url": "http://example.com/file.zip",
    "filename": "file.zip"
}
```

#### Pause Download

```json
{
    "command": "pause",
    "gid": "download_gid_here"
}
```

#### Resume Download

```json
{
    "command": "resume", 
    "gid": "download_gid_here"
}
```

#### Remove Download

```json
{
    "command": "remove",
    "gid": "download_gid_here"
}
```

#### Get Download Status

```json
{
    "command": "status",
    "gid": "download_gid_here"
}
```

#### List All Downloads

```json
{
    "command": "list"
}
```

### Make script executable

```bash
chmod +x downloader.py
```

### Monitoring Downloads

Check aria2c logs directly:

```bash
# Follow aria2c daemon logs
tail -f /path/to/aria2c.log

# Check Python helper logs
tail -f /path/to/downloader.log
```

## Key Features

### Reliability

- **aria2c retry logic**: Configurable retry attempts (default: 10) with exponential backoff
- **Resume capability**: Automatic resume of interrupted downloads
- **Error handling**: Comprehensive logging and graceful error responses

### Performance

- **Concurrent downloads**: Configurable parallel download limits
- **Multi-connection**: Multiple connections per server for faster downloads
- **Efficient protocol**: Direct RPC communication, no subprocess overhead

### Security

- **RPC authentication**: Secret-based authentication for daemon access
- **Local-only binding**: Daemon listens on localhost by default
- **Controlled access**: CORS restrictions prevent unauthorized web access

## Monitoring and Debugging

### Log Locations

- **Python helper**: `/path/to/downloader.log` (configurable)
- **aria2c daemon**: Specified in daemon start command

### Common Issues

1. **Daemon not running**: Check if aria2c daemon is active

   ```bash
   pidof aria2c
   ```

2. **Connection refused**: Verify RPC port and secret configuration

3. **Permission errors**: Ensure download directory is writable

4. **Infinite retries**: Use `--max-tries=N` instead of `--max-tries=0`

### Stopping Downloads

```bash
# Stop daemon
kill $(pidof aria2c)
# or
sudo systemctl stop aria2c
```

Stopping specific downloads will be added in the future through browser extension UI

## Browser Extension Integration

The helper is designed for native messaging integration:

1. **Manifest registration**: Register the helper in browser extension manifest
2. **Native messaging**: Use browser's native messaging API to send commands
3. **Response handling**: Process JSON responses for UI updates

## Development

### Project Structure

```graphql
RapidPyFetch/
├── venv/              # Virtual environment
├── extension/         # Unpackaged extension to be loaded by the browser
│ ├── manifest.json
│ ├── assets/          # extension logo
│ ├── background/
| | └── sw.js          # service worker
│ └── popup/           # extension popup UI (html file)
├── host_manifest/     # contains native messaging host configuration file 
├── native_app/
│ ├── aria2c.service     # Example aria2c service script
│ ├── start_aria2c.sh    # Example bash script for starting aria2c daemon manually
│ ├── requirements.in    # Lists python script's external library requirements
│ ├── requirements.txt   # Requirements file generated from `uv pip compile requirements.in >  requirements.txt`
│ ├── .env.example       # Example environment file
│ ├── downloader.py      # Main Python helper
│ └── utils.py           # Utility functions (get_message, send_message, etc.)
├── .gitignore         # Gitignore configuration
└── README.md          # This file
```

### Extending Functionality

To add new commands:

1. Add command case in `process_command()` function
2. Implement corresponding method in `DownloadManager` class
3. Update this README with new command documentation

## Why This Architecture?

### Eliminated Complexity

- **No background threads**: Removed monitoring threads that added overhead
- **No custom retry logic**: Leverages aria2c's battle-tested retry mechanisms
- **Single-purpose execution**: One command per process invocation

### Leveraged Strengths

- **aria2c reliability**: Proven download utility with robust error handling
- **RPC efficiency**: Direct API communication without subprocess overhead
- **Native logging**: aria2c's built-in logging is comprehensive and configurable

### Practical Benefits

- **Easier debugging**: Clear separation of concerns, focused logging
- **Better performance**: No Python overhead for download monitoring
- **Simpler maintenance**: Less custom code means fewer potential bugs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:

- Check aria2c logs first
- Review Python helper logs
- Verify daemon configuration
- Ensure RPC connectivity

---

*Built with a focus on simplicity, reliability, and practical software engineering.*
