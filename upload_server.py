from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import re
import sys
import argparse

UPLOAD_DIR = "./uploads"
PORT = 8000
SERVER_KEY = None  # Will be set from command line argument

os.makedirs(UPLOAD_DIR, exist_ok=True)

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

class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
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
        <h2>Upload Files</h2>
        <div id="drop-area">
            <div style="margin-bottom: 15px;">
                <label for="encryption-key" style="display: block; margin-bottom: 5px; font-weight: bold;">Encryption Key:</label>
                <input type="password" id="encryption-key" placeholder="Enter encryption key" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
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

        <script>
            const dropArea = document.getElementById('drop-area');
            const fileElem = document.getElementById('fileElem');
            const form = document.getElementById('form');
            const responseBox = document.getElementById('response');
            const statusDiv = document.getElementById('status');
            const fileListDiv = document.getElementById('file-list');

            let selectedFiles = [];

            function getEncryptionKey() {
                const keyInput = document.getElementById('encryption-key');
                return keyInput.value.trim();
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
                  
                  if (!encryptionKey) {
                      statusDiv.innerHTML = 'Please enter an encryption key!';
                      statusDiv.style.color = '#dc3545';
                      return;
                  }
                  
                  dropArea.classList.add('uploading');
                  statusDiv.innerHTML = 'Encrypting and uploading files...';
                  statusDiv.style.color = '';
                  
                  const formData = new FormData();
                  
                  // Encrypt files before uploading
                  for (let i = 0; i < files.length; i++) {
                      const file = files[i];
                      updateFileStatus(i, 'Encrypting...', '#ff6b35');
                      
                      const encryptedFile = await encryptFile(file, encryptionKey);
                      formData.append('file', encryptedFile);
                      formData.append('original_name', file.name);  // Send original filename
                      
                      updateFileStatus(i, 'Uploading...', '#ffc107');
                  }
                 
                 try {
                     const res = await fetch('/', {
                         method: 'POST',
                         body: formData
                     });
                     const text = await res.text();
                     
                     Array.from(files).forEach((file, index) => {
                         updateFileStatus(index, 'Uploaded', '#28a745');
                     });
                     
                     statusDiv.innerHTML = 'Upload completed!';
                     responseBox.innerHTML = "<pre>" + text + "</pre>";
                 } catch (error) {
                     statusDiv.innerHTML = 'Upload failed!';
                     responseBox.innerHTML = "<pre>Error: " + error.message + "</pre>";
                 } finally {
                     dropArea.classList.remove('uploading');
                 }
             }

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

        uploaded_files = []
        original_names = []
        current_field = None

        while remainbytes > 0:
            header_line = self.rfile.readline()
            remainbytes -= len(header_line)
            
            if b'name="original_name"' in header_line:
                current_field = 'original_name'
                # Skip the rest of headers
                while True:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if line.strip() == b"":
                        break
                
                # Read the original filename
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
                
                original_names.append(data.decode().strip())
                continue
            
            elif b'filename="' in header_line:
                current_field = 'file'
                filename = re.findall(r'filename="([^"]+)"', header_line.decode())[0]
                filename = os.path.basename(filename)

                # Skip the rest of headers
                while True:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if line.strip() == b"":
                        break

                # Read encrypted file data
                encrypted_data = b''
                preline = self.rfile.readline()
                remainbytes -= len(preline)
                while remainbytes > 0:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if boundary in line:
                        preline = preline.rstrip(b"\r\n")
                        encrypted_data += preline
                        break
                    else:
                        encrypted_data += preline
                        preline = line

                # Decrypt the file data
                decrypted_data = decrypt_file_data(encrypted_data)
                if decrypted_data is None:
                    self.send_error(500, "Failed to decrypt file")
                    return

                # Use original filename if available
                if original_names:
                    original_filename = original_names.pop(0)
                else:
                    original_filename = filename.replace('.enc', '')

                out_path = os.path.join(UPLOAD_DIR, original_filename)
                with open(out_path, 'wb') as f:
                    f.write(decrypted_data)

                uploaded_files.append(original_filename)
            else:
                break

        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"Uploaded and decrypted files:\n".encode())
        for f in uploaded_files:
            self.wfile.write(f" - {f}\n".encode())

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
