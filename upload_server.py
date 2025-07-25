#!/usr/bin/env python3
"""
ExfilServer - Secure File Upload Server with Encryption

SECURITY FIXES IMPLEMENTED:
- Filename sanitization to prevent directory traversal attacks
- Path validation to ensure files stay within designated directories
- File extension validation (DISABLED - allows all file types)
- File size limits to prevent resource exhaustion
- Input validation for chunk parameters
- Security event logging for monitoring
- Protection against reserved filename attacks
- Client IP tracking for security events

VULNERABILITIES ADDRESSED:
- CVE-like: Local File Inclusion (LFI) via path traversal
- CVE-like: Arbitrary file write via malicious filenames
- CVE-like: Resource exhaustion via large file uploads
- CVE-like: Filename injection attacks
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import re
import sys
import argparse
import json
import urllib.parse
import string
import datetime

UPLOAD_DIR = "./uploads"
CHUNK_DIR = "./chunks"
PORT = 8000
SERVER_KEY = None  # Will be set from command line argument

# Security configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
MAX_FILENAME_LENGTH = 255
ALLOWED_EXTENSIONS = None  # Allow all file types - set to None to disable extension filtering

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

# Dictionary to track chunk uploads
chunk_tracker = {}

def log_security_event(event_type, details, client_ip="unknown"):
    """Log security events for monitoring"""
    timestamp = datetime.datetime.now().isoformat()
    log_message = f"[{timestamp}] SECURITY EVENT - {event_type}: {details} (Client: {client_ip})"
    print(log_message)
    # In production, this should write to a proper log file
    try:
        with open("security.log", "a") as log_file:
            log_file.write(log_message + "\n")
    except Exception:
        pass  # Don't fail if logging fails

def validate_file_extension(filename):
    """Validate file extension against allowed list"""
    if not filename:
        return False
    
    # If ALLOWED_EXTENSIONS is None, allow all file types
    if ALLOWED_EXTENSIONS is None:
        return True
    
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

def sanitize_filename(filename):
    """Sanitize filename to prevent directory traversal and other security issues"""
    if not filename:
        return "unnamed_file"
    
    # Remove path components and keep only the basename
    filename = os.path.basename(filename)
    
    # Remove or replace dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Prevent reserved names on Windows
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    if filename.upper() in reserved_names:
        filename = f"file_{filename}"
    
    # Prevent empty filenames or just dots
    if not filename or filename in ['.', '..']:
        filename = 'unnamed_file'
    
    # Limit filename length
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        filename = name[:MAX_FILENAME_LENGTH-10-len(ext)] + ext
    
    return filename

def validate_chunk_params(chunk_index, total_chunks):
    """Validate chunk parameters to prevent abuse"""
    try:
        chunk_index = int(chunk_index)
        total_chunks = int(total_chunks)
        
        if chunk_index < 0 or total_chunks < 1:
            return False, "Invalid chunk parameters"
        
        if chunk_index >= total_chunks:
            return False, "Chunk index exceeds total chunks"
        
        if total_chunks > 10000:  # Reasonable limit
            return False, "Too many chunks"
        
        return True, (chunk_index, total_chunks)
    except (ValueError, TypeError):
        return False, "Invalid chunk parameter format"

def decrypt_file_data(encrypted_data):
    """Decrypt file data using XOR with server key"""
    try:
        if SERVER_KEY is None:
            print("Server key not set")
            return None
            
        key_bytes = SERVER_KEY.encode()
        decrypted = bytearray()
        
        for i, byte in enumerate(encrypted_data):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return bytes(decrypted)
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

def encrypt_file_data(file_data):
    """Encrypt file data using XOR with server key for download"""
    try:
        if SERVER_KEY is None:
            print("Server key not set")
            return None
            
        key_bytes = SERVER_KEY.encode()
        encrypted = bytearray()
        
        for i, byte in enumerate(file_data):
            encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return bytes(encrypted)
    except Exception as e:
        print(f"Encryption error: {e}")
        return None

def encrypt_filename(filename):
    """Encrypt filename using XOR with server key"""
    try:
        if SERVER_KEY is None:
            return filename
            
        key_bytes = SERVER_KEY.encode()
        filename_bytes = filename.encode('utf-8')
        encrypted = bytearray()
        
        for i, byte in enumerate(filename_bytes):
            encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        # Convert to hex string for safe transmission
        return encrypted.hex()
    except Exception as e:
        print(f"Filename encryption error: {e}")
        return filename

def decrypt_filename(encrypted_hex):
    """Decrypt filename from hex string using XOR with server key"""
    try:
        if SERVER_KEY is None:
            return encrypted_hex
            
        key_bytes = SERVER_KEY.encode()
        encrypted_bytes = bytes.fromhex(encrypted_hex)
        decrypted = bytearray()
        
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
        
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"Filename decryption error: {e}")
        return encrypted_hex

def reassemble_chunks(original_filename, total_chunks):
    """Reassemble chunks into the original file"""
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = sanitize_filename(original_filename)
        
        chunk_files = []
        for i in range(total_chunks):
            # Use sanitized filename for chunk paths
            chunk_path = os.path.join(CHUNK_DIR, f"{safe_filename}.chunk{i}")
            if not os.path.exists(chunk_path):
                print(f"Missing chunk {i} for {safe_filename}")
                return False
            chunk_files.append(chunk_path)
        
        # Reassemble the file with sanitized filename
        output_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        # Ensure the output path is within the upload directory
        if not os.path.abspath(output_path).startswith(os.path.abspath(UPLOAD_DIR)):
            log_security_event("PATH_TRAVERSAL_ATTEMPT", f"Attempted path traversal in reassemble_chunks: {original_filename} -> {output_path}")
            print(f"Security violation: attempted path traversal for {original_filename}")
            return False
        
        with open(output_path, 'wb') as output_file:
            for chunk_path in chunk_files:
                with open(chunk_path, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
        
        # Clean up chunk files
        for chunk_path in chunk_files:
            os.remove(chunk_path)
        
        # Remove from tracker (use original filename as key)
        if original_filename in chunk_tracker:
            del chunk_tracker[original_filename]
        
        print(f"Successfully reassembled {safe_filename} from {total_chunks} chunks")
        return True
    except Exception as e:
        print(f"Error reassembling chunks for {original_filename}: {e}")
        return False

class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL path
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path == '/files':
            self.handle_file_list()
        elif path.startswith('/download/'):
            filename = path[10:]  # Remove '/download/' prefix
            self.handle_file_download(filename)
        else:
            self.handle_main_page()
    
    def handle_file_list(self):
        """Return JSON list of uploaded files with encrypted filenames"""
        try:
            files = []
            if os.path.exists(UPLOAD_DIR):
                for filename in os.listdir(UPLOAD_DIR):
                    if not filename.startswith('.'):  # Skip all dot files (.gitkeep, .DS_Store, etc.)
                        filepath = os.path.join(UPLOAD_DIR, filename)
                        if os.path.isfile(filepath):
                            file_size = os.path.getsize(filepath)
                            encrypted_name = encrypt_filename(filename)
                            files.append({
                                'name': encrypted_name,
                                'original_name': filename,  # Keep for server-side reference
                                'size': file_size,
                                'size_kb': round(file_size / 1024, 1)
                            })
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode())
        except Exception as e:
            print(f"Error listing files: {e}")
            self.send_error(500, "Failed to list files")
    
    def handle_file_download(self, encrypted_filename):
        """Handle file download with server-side encryption"""
        try:
            # Decrypt the filename first
            filename = decrypt_filename(encrypted_filename)
            # Sanitize filename to prevent directory traversal
            filename = os.path.basename(filename)
            filepath = os.path.join(UPLOAD_DIR, filename)
            
            if not os.path.exists(filepath):
                self.send_error(404, "File not found")
                return
            
            # Read and encrypt the file
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            encrypted_data = encrypt_file_data(file_data)
            if encrypted_data is None:
                self.send_error(500, "Failed to encrypt file")
                return
            
            # Send encrypted file
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}.enc"')
            self.send_header('Content-Length', str(len(encrypted_data)))
            self.end_headers()
            self.wfile.write(encrypted_data)
            
            print(f"Downloaded file: {filename} (encrypted)")
            
        except Exception as e:
            print(f"Download error: {e}")
            self.send_error(500, "Download failed")
    
    def handle_main_page(self):
        html = '''
        <html><head><title>File Upload</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            #drop-area {
                border: 2px dashed #ccc;
                border-radius: 20px;
                width: 100%;
                max-width: 600px;
                padding: 20px;
                text-align: center;
                margin: auto;
                transition: all 0.3s ease;
            }
            #drop-area.highlight { 
                border-color: #007bff; 
                background-color: #f0f8ff;
            }
            #drop-area.uploading {
                border-color: #28a745;
                background-color: #f0fff0;
            }
            input[type="file"] { display: none; }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                cursor: pointer;
                background: #007bff;
                color: white;
                border-radius: 5px;
                margin: 5px;
            }
            .file-list {
                margin-top: 15px;
                text-align: left;
            }
            .file-item {
                padding: 8px;
                margin: 5px 0;
                background: #f8f9fa;
                border-radius: 5px;
                border-left: 4px solid #007bff;
            }
            .file-item.uploading {
                border-left-color: #ffc107;
                background: #fff3cd;
            }
            .file-item.uploaded {
                border-left-color: #28a745;
                background: #d4edda;
            }
            .status {
                font-weight: bold;
                margin-top: 10px;
            }
        </style>
        </head><body>
        <h2>File Upload & Download Server</h2>
        
        <!-- Upload Section -->
        <div style="margin-bottom: 30px;">
            <h3>Upload Files</h3>
            <div id="drop-area">
            <div style="margin-bottom: 15px;">
                <label for="encryption-key" style="display: block; margin-bottom: 5px; font-weight: bold;">Encryption Key:</label>
                <input type="password" id="encryption-key" placeholder="Enter encryption key" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label for="chunk-count" style="display: block; margin-bottom: 5px; font-weight: bold;">Number of Chunks:</label>
                <input type="number" id="chunk-count" value="1" min="1" max="1000" placeholder="Number of chunks" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                <small style="color: #666; display: block; margin-top: 2px;">Split each file into this many chunks (1 = no chunking)</small>
            </div>
            <div style="margin-bottom: 15px;">
                <label for="chunk-delay" style="display: block; margin-bottom: 5px; font-weight: bold;">Delay Between Chunks (ms):</label>
                <input type="number" id="chunk-delay" value="0" min="0" max="10000" placeholder="Delay in milliseconds" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                <small style="color: #666; display: block; margin-top: 2px;">Delay between chunk uploads to control upload rate</small>
            </div>
            <form id="form" enctype="multipart/form-data" method="post">
                <input type="file" id="fileElem" name="file" multiple>
                <label class="btn" for="fileElem">Select files</label>
                <input class="btn" type="submit" value="Upload">
            </form>
            <p>Or drag and drop files here</p>
            <div class="status" id="status"></div>
            <div class="file-list" id="file-list"></div>
            </div>
            <div id="response"></div>
        </div>
        
        <!-- Download Section -->
        <div style="margin-bottom: 30px;">
            <h3>Download Files</h3>
            <div style="margin-bottom: 15px;">
                <label for="download-key" style="display: block; margin-bottom: 5px; font-weight: bold;">Decryption Key:</label>
                <input type="password" id="download-key" placeholder="Enter decryption key" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
            </div>
            <button onclick="refreshFileList()" class="btn" style="margin-bottom: 15px;">Refresh File List</button>
            <div id="download-status" class="status"></div>
            <div id="available-files" class="file-list"></div>
        </div>

        <script>
            const dropArea = document.getElementById('drop-area');
            const fileElem = document.getElementById('fileElem');
            const form = document.getElementById('form');
            const responseBox = document.getElementById('response');
            const statusDiv = document.getElementById('status');
            const fileListDiv = document.getElementById('file-list');
            const downloadStatusDiv = document.getElementById('download-status');
            const availableFilesDiv = document.getElementById('available-files');

            let selectedFiles = [];
            let availableFiles = [];

            function getEncryptionKey() {
                const keyInput = document.getElementById('encryption-key');
                return keyInput.value.trim();
            }

            function getChunkCount() {
                const chunkInput = document.getElementById('chunk-count');
                return parseInt(chunkInput.value) || 1;
            }

            function getChunkDelay() {
                const delayInput = document.getElementById('chunk-delay');
                return parseInt(delayInput.value) || 0;
            }

            function getDownloadKey() {
                const keyInput = document.getElementById('download-key');
                return keyInput.value.trim();
            }

            function sleep(ms) {
                return new Promise(resolve => setTimeout(resolve, ms));
            }

            // Simple XOR encryption for client-side obfuscation
            function encryptData(data, key) {
                const keyBytes = new TextEncoder().encode(key);
                const dataBytes = new Uint8Array(data);
                const encrypted = new Uint8Array(dataBytes.length);
                
                for (let i = 0; i < dataBytes.length; i++) {
                    encrypted[i] = dataBytes[i] ^ keyBytes[i % keyBytes.length];
                }
                
                return encrypted;
            }

            // Simple XOR decryption for client-side (same as encryption)
            function decryptData(encryptedData, key) {
                const keyBytes = new TextEncoder().encode(key);
                const dataBytes = new Uint8Array(encryptedData);
                const decrypted = new Uint8Array(dataBytes.length);
                
                for (let i = 0; i < dataBytes.length; i++) {
                    decrypted[i] = dataBytes[i] ^ keyBytes[i % keyBytes.length];
                }
                
                return decrypted;
            }

            // Decrypt filename from hex string using XOR
            function decryptFilename(encryptedHex, key) {
                try {
                    const keyBytes = new TextEncoder().encode(key);
                    const encryptedBytes = new Uint8Array(encryptedHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
                    const decrypted = new Uint8Array(encryptedBytes.length);
                    
                    for (let i = 0; i < encryptedBytes.length; i++) {
                        decrypted[i] = encryptedBytes[i] ^ keyBytes[i % keyBytes.length];
                    }
                    
                    return new TextDecoder().decode(decrypted);
                } catch (error) {
                    console.error('Filename decryption error:', error);
                    return encryptedHex; // Return original if decryption fails
                }
            }

            async function encryptFile(file, key) {
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const encrypted = encryptData(e.target.result, key);
                        const blob = new Blob([encrypted], { type: 'application/octet-stream' });
                        resolve(new File([blob], file.name + '.enc', { type: 'application/octet-stream' }));
                    };
                    reader.readAsArrayBuffer(file);
                });
            }

            function splitFileIntoChunks(file, chunkCount) {
                const chunks = [];
                const chunkSize = Math.ceil(file.size / chunkCount);
                
                for (let i = 0; i < chunkCount; i++) {
                    const start = i * chunkSize;
                    const end = Math.min(start + chunkSize, file.size);
                    const chunk = file.slice(start, end);
                    chunks.push(chunk);
                }
                
                return chunks;
            }

            async function encryptFileChunk(chunk, key, originalFileName, chunkIndex, totalChunks) {
                return new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const encrypted = encryptData(e.target.result, key);
                        const blob = new Blob([encrypted], { type: 'application/octet-stream' });
                        const chunkFileName = `${originalFileName}.chunk${chunkIndex}.enc`;
                        resolve(new File([blob], chunkFileName, { type: 'application/octet-stream' }));
                    };
                    reader.readAsArrayBuffer(chunk);
                });
            }

            function updateFileList() {
                fileListDiv.innerHTML = '';
                selectedFiles.forEach((file, index) => {
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <span>${file.name} (${(file.size / 1024).toFixed(1)} KB)</span>
                        <span style="float: right; color: #007bff;">Ready</span>
                    `;
                    fileItem.id = `file-${index}`;
                    fileListDiv.appendChild(fileItem);
                });
                
                if (selectedFiles.length > 0) {
                    statusDiv.innerHTML = `${selectedFiles.length} file(s) selected`;
                } else {
                    statusDiv.innerHTML = '';
                }
            }

            function updateFileStatus(index, status, color) {
                const fileItem = document.getElementById(`file-${index}`);
                if (fileItem) {
                    const statusSpan = fileItem.querySelector('span:last-child');
                    statusSpan.textContent = status;
                    statusSpan.style.color = color;
                    
                    if (status === 'Uploading...') {
                        fileItem.className = 'file-item uploading';
                    } else if (status === 'Uploaded') {
                        fileItem.className = 'file-item uploaded';
                    }
                }
            }

            async function uploadFiles(files) {
                  const encryptionKey = getEncryptionKey();
                  const chunkCount = getChunkCount();
                  const chunkDelay = getChunkDelay();
                  
                  if (!encryptionKey) {
                      statusDiv.innerHTML = 'Please enter an encryption key!';
                      statusDiv.style.color = '#dc3545';
                      return;
                  }
                  
                  dropArea.classList.add('uploading');
                  const delayText = chunkDelay > 0 ? ` (${chunkDelay}ms delay)` : '';
                  statusDiv.innerHTML = `Processing ${files.length} file(s) with ${chunkCount} chunk(s) each${delayText}...`;
                  statusDiv.style.color = '';
                  
                  try {
                      for (let i = 0; i < files.length; i++) {
                          const file = files[i];
                          updateFileStatus(i, 'Splitting...', '#ff6b35');
                          
                          if (chunkCount === 1) {
                              // No chunking - use original method
                              updateFileStatus(i, 'Encrypting...', '#ff6b35');
                              const encryptedFile = await encryptFile(file, encryptionKey);
                              
                              const formData = new FormData();
                              formData.append('file', encryptedFile);
                              formData.append('original_name', file.name);
                              
                              updateFileStatus(i, 'Uploading...', '#ffc107');
                              
                              const res = await fetch('/', {
                                  method: 'POST',
                                  body: formData
                              });
                              
                              if (res.ok) {
                                  updateFileStatus(i, 'Uploaded', '#28a745');
                              } else {
                                  updateFileStatus(i, 'Failed', '#dc3545');
                              }
                          } else {
                              // Chunked upload
                              const chunks = splitFileIntoChunks(file, chunkCount);
                              updateFileStatus(i, `Encrypting ${chunks.length} chunks...`, '#ff6b35');
                               
                               for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
                                  const chunk = chunks[chunkIndex];
                                  const encryptedChunk = await encryptFileChunk(chunk, encryptionKey, file.name, chunkIndex, chunks.length);
                                  
                                  const formData = new FormData();
                                  formData.append('file', encryptedChunk);
                                  formData.append('original_name', file.name);
                                  formData.append('chunk_index', chunkIndex.toString());
                                  formData.append('total_chunks', chunks.length.toString());
                                  
                                  updateFileStatus(i, `Uploading chunk ${chunkIndex + 1}/${chunks.length}...`, '#ffc107');
                                  
                                  const res = await fetch('/', {
                                      method: 'POST',
                                      body: formData
                                  });
                                  
                                  if (!res.ok) {
                                      updateFileStatus(i, `Failed at chunk ${chunkIndex + 1}`, '#dc3545');
                                      throw new Error(`Failed to upload chunk ${chunkIndex + 1} of ${file.name}`);
                                  }
                                  
                                  // Add delay between chunks if specified
                                  if (chunkDelay > 0 && chunkIndex < chunks.length - 1) {
                                      await sleep(chunkDelay);
                                  }
                              }
                              
                              updateFileStatus(i, 'Uploaded', '#28a745');
                          }
                      }
                      
                      statusDiv.innerHTML = 'All uploads completed!';
                      responseBox.innerHTML = "<pre>All files uploaded successfully</pre>";
                      // Refresh file list to show newly uploaded files
                      refreshFileList();
                  } catch (error) {
                      statusDiv.innerHTML = 'Upload failed!';
                      responseBox.innerHTML = "<pre>Error: " + error.message + "</pre>";
                  } finally {
                      dropArea.classList.remove('uploading');
                  }
             }

            // File listing and download functions
            async function refreshFileList() {
                try {
                    downloadStatusDiv.innerHTML = 'Loading file list...';
                    downloadStatusDiv.style.color = '';
                    
                    const response = await fetch('/files');
                    if (!response.ok) {
                        throw new Error('Failed to fetch file list');
                    }
                    
                    availableFiles = await response.json();
                    displayFileList();
                    
                    downloadStatusDiv.innerHTML = `Found ${availableFiles.length} file(s)`;
                } catch (error) {
                    downloadStatusDiv.innerHTML = 'Failed to load file list: ' + error.message;
                    downloadStatusDiv.style.color = '#dc3545';
                    availableFilesDiv.innerHTML = '';
                }
            }

            function displayFileList() {
                availableFilesDiv.innerHTML = '';
                
                if (availableFiles.length === 0) {
                    availableFilesDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">No files available for download</div>';
                    return;
                }
                
                availableFiles.forEach((file, index) => {
                    const downloadKey = getDownloadKey();
                    let displayName = file.name;
                    
                    // Try to decrypt filename for display if download key is provided
                    if (downloadKey) {
                        try {
                            displayName = decryptFilename(file.name, downloadKey);
                        } catch (error) {
                            displayName = '[Encrypted: ' + file.name.substring(0, 16) + '...]';
                        }
                    } else {
                        displayName = '[Encrypted: ' + file.name.substring(0, 16) + '...]';
                    }
                    
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <span>${displayName} (${file.size_kb} KB)</span>
                        <button onclick="downloadFile('${file.name}', '${displayName}')" class="btn" style="float: right; padding: 5px 10px; font-size: 12px;">Download</button>
                    `;
                    availableFilesDiv.appendChild(fileItem);
                });
            }

            async function downloadFile(encryptedFilename, displayName) {
                const downloadKey = getDownloadKey();
                
                if (!downloadKey) {
                    downloadStatusDiv.innerHTML = 'Please enter a decryption key!';
                    downloadStatusDiv.style.color = '#dc3545';
                    return;
                }
                
                try {
                    // Decrypt the filename to get the original name for saving
                    const originalFilename = decryptFilename(encryptedFilename, downloadKey);
                    
                    downloadStatusDiv.innerHTML = `Downloading ${displayName}...`;
                    downloadStatusDiv.style.color = '';
                    
                    // Download encrypted file using the encrypted filename
                    const response = await fetch(`/download/${encodeURIComponent(encryptedFilename)}`);
                    if (!response.ok) {
                        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
                    }
                    
                    const encryptedData = await response.arrayBuffer();
                    
                    downloadStatusDiv.innerHTML = `Decrypting ${displayName}...`;
                    
                    // Decrypt the file
                    const decryptedData = decryptData(encryptedData, downloadKey);
                    
                    // Create and trigger download with original filename
                    const blob = new Blob([decryptedData]);
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = originalFilename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    downloadStatusDiv.innerHTML = `Successfully downloaded ${displayName}`;
                    downloadStatusDiv.style.color = '#28a745';
                    
                } catch (error) {
                    downloadStatusDiv.innerHTML = `Download failed: ${error.message}`;
                    downloadStatusDiv.style.color = '#dc3545';
                }
            }

            // Load file list on page load
            window.addEventListener('load', refreshFileList);
            
            // Refresh file list when download key changes to show decrypted filenames
            document.getElementById('download-key').addEventListener('input', function() {
                if (availableFiles && availableFiles.length > 0) {
                    displayFileList();
                }
            });

            ;['dragenter', 'dragover'].forEach(event => {
                dropArea.addEventListener(event, e => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropArea.classList.add('highlight');
                }, false);
            });

            ;['dragleave', 'drop'].forEach(event => {
                dropArea.addEventListener(event, e => {
                    e.preventDefault();
                    e.stopPropagation();
                    dropArea.classList.remove('highlight');
                }, false);
            });

            dropArea.addEventListener('drop', e => {
                const files = e.dataTransfer.files;
                fileElem.files = files;
                selectedFiles = Array.from(files);
                updateFileList();
                // Automatically upload after dropping
                uploadFiles(files);
            });

            fileElem.addEventListener('change', e => {
                selectedFiles = Array.from(e.target.files);
                updateFileList();
            });

            form.addEventListener('submit', async e => {
                e.preventDefault();
                if (selectedFiles.length > 0) {
                    await uploadFiles(selectedFiles);
                }
            });
        </script>
        </body></html>
        '''
        self.send_response(200)
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self):
        content_type = self.headers.get('Content-Type')
        if not content_type or not content_type.startswith('multipart/form-data'):
            self.send_error(400, "Expected multipart/form-data")
            return

        boundary = re.findall("boundary=(.*)", content_type)[0].encode()
        remainbytes = int(self.headers['Content-length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            self.send_error(400, "Content does not start with boundary")
            return

        form_data = {}
        
        # Parse multipart form data
        while remainbytes > 0:
            header_line = self.rfile.readline()
            remainbytes -= len(header_line)
            
            if b'name="' in header_line:
                # Extract field name
                field_name_match = re.search(b'name="([^"]+)"', header_line)
                if not field_name_match:
                    continue
                    
                field_name = field_name_match.group(1).decode()
                
                # Skip remaining headers
                while True:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if line.strip() == b"":
                        break
                
                # Read field data
                data = b''
                preline = self.rfile.readline()
                remainbytes -= len(preline)
                while remainbytes > 0:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if boundary in line:
                        preline = preline.rstrip(b"\r\n")
                        data += preline
                        break
                    else:
                        data += preline
                        preline = line
                
                if field_name == 'file':
                    form_data['file_data'] = data
                else:
                    form_data[field_name] = data.decode().strip()
            else:
                break
        
        # Process the upload
        try:
            original_name = form_data.get('original_name')
            chunk_index = form_data.get('chunk_index')
            total_chunks = form_data.get('total_chunks')
            file_data = form_data.get('file_data')
            
            if not original_name or not file_data:
                self.send_error(400, "Missing required fields")
                return
            
            # Sanitize filename to prevent directory traversal
            safe_filename = sanitize_filename(original_name)
            if not safe_filename:
                log_security_event("INVALID_FILENAME", f"Invalid filename rejected: {original_name}", self.client_address[0])
                self.send_error(400, "Invalid filename")
                return
            
            # Log if filename was modified during sanitization
            if safe_filename != original_name:
                log_security_event("FILENAME_SANITIZED", f"Filename sanitized: '{original_name}' -> '{safe_filename}'", self.client_address[0])
            
            # Validate file extension
            if not validate_file_extension(safe_filename):
                log_security_event("INVALID_FILE_EXTENSION", f"File extension not allowed: {safe_filename}", self.client_address[0])
                self.send_error(400, "File extension not allowed")
                return
            
            # Check file size limit
            if len(file_data) > MAX_FILE_SIZE:
                log_security_event("FILE_SIZE_EXCEEDED", f"File size exceeded limit: {len(file_data)} bytes for {safe_filename}", self.client_address[0])
                self.send_error(400, f"File size exceeds limit of {MAX_FILE_SIZE // (1024*1024)}MB")
                return
            
            # Decrypt the file data
            decrypted_data = decrypt_file_data(file_data)
            if decrypted_data is None:
                self.send_error(500, "Failed to decrypt file")
                return
            
            if chunk_index is not None and total_chunks is not None:
                # Validate chunk parameters
                is_valid, result = validate_chunk_params(chunk_index, total_chunks)
                if not is_valid:
                    self.send_error(400, f"Invalid chunk parameters: {result}")
                    return
                
                chunk_index, total_chunks = result
                
                # Initialize chunk tracker for this file (use original name as key)
                if original_name not in chunk_tracker:
                    chunk_tracker[original_name] = {
                        'total_chunks': total_chunks,
                        'received_chunks': set(),
                        'safe_filename': safe_filename
                    }
                
                # Verify chunk parameters match previous chunks
                if chunk_tracker[original_name]['total_chunks'] != total_chunks:
                    self.send_error(400, "Chunk count mismatch")
                    return
                
                # Save chunk with sanitized filename
                chunk_path = os.path.join(CHUNK_DIR, f"{safe_filename}.chunk{chunk_index}")
                
                # Ensure the chunk path is within the chunk directory
                if not os.path.abspath(chunk_path).startswith(os.path.abspath(CHUNK_DIR)):
                    log_security_event("PATH_TRAVERSAL_ATTEMPT", f"Attempted path traversal in chunk upload: {chunk_path}", self.client_address[0])
                    self.send_error(400, "Security violation: invalid chunk path")
                    return
                
                with open(chunk_path, 'wb') as f:
                    f.write(decrypted_data)
                
                # Track received chunk
                chunk_tracker[original_name]['received_chunks'].add(chunk_index)
                
                print(f"Received chunk {chunk_index + 1}/{total_chunks} for {safe_filename}")
                
                # Check if all chunks received
                if len(chunk_tracker[original_name]['received_chunks']) == total_chunks:
                    if reassemble_chunks(original_name, total_chunks):
                        response_msg = f"File {safe_filename} successfully assembled from {total_chunks} chunks"
                    else:
                        response_msg = f"Failed to assemble {safe_filename}"
                        self.send_error(500, response_msg)
                        return
                else:
                    response_msg = f"Chunk {chunk_index + 1}/{total_chunks} received for {safe_filename}"
            else:
                # Handle regular upload (no chunking) with sanitized filename
                out_path = os.path.join(UPLOAD_DIR, safe_filename)
                
                # Ensure the output path is within the upload directory
                if not os.path.abspath(out_path).startswith(os.path.abspath(UPLOAD_DIR)):
                    log_security_event("PATH_TRAVERSAL_ATTEMPT", f"Attempted path traversal in file upload: {out_path}", self.client_address[0])
                    self.send_error(400, "Security violation: invalid upload path")
                    return
                
                with open(out_path, 'wb') as f:
                    f.write(decrypted_data)
                
                response_msg = f"File {safe_filename} uploaded successfully"
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(response_msg.encode())
            
        except Exception as e:
            print(f"Upload error: {e}")
            self.send_error(500, f"Upload failed: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Encrypted File Upload Server')
    parser.add_argument('--key', required=True, help='Server decryption key')
    parser.add_argument('--port', type=int, default=PORT, help=f'Port to run server on (default: {PORT})')
    
    args = parser.parse_args()
    
    # Set global server key
    SERVER_KEY = args.key
    PORT = args.port
    
    print(f"Serving on http://localhost:{PORT}/")
    print(f"Server key configured for decryption")
    server = HTTPServer(('0.0.0.0', PORT), UploadHandler)
    server.serve_forever()
