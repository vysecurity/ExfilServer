<img src="logo.png" alt="ExfilServer Logo" width="200">

# ExfilServer
Client-side Encrypted Upload Server Python Script

## Overview

ExfilServer is a secure file upload server that provides client-side encryption and automatic upload functionality. It features a modern web interface with drag-and-drop support, real-time file status indicators, and XOR-based encryption for file obfuscation during transmission.

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
3. Either:
   - Click "Select files" to choose files manually, then click "Upload"
   - Drag and drop files directly into the drop area for automatic upload

### File Processing Flow

1. **Client**: User enters encryption key and selects/drops files
2. **Encryption**: Files are encrypted in the browser using XOR cipher
3. **Upload**: Encrypted files are transmitted to the server
4. **Decryption**: Server decrypts files using the specified server key
5. **Storage**: Decrypted files are saved with original filenames

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

Developed by VYSecurity for secure file collection and transfer scenarios.
