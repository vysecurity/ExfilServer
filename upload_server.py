from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import re
import sys
import argparse

UPLOAD_DIR = "./uploads"
CHUNK_DIR = "./chunks"
PORT = 8000
SERVER_KEY = None  # Will be set from command line argument

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHUNK_DIR, exist_ok=True)

# Dictionary to track chunk uploads
chunk_tracker = {}

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

def reassemble_chunks(original_filename, total_chunks):
    """Reassemble chunks into the original file"""
    try:
        chunk_files = []
        for i in range(total_chunks):
            chunk_path = os.path.join(CHUNK_DIR, f"{original_filename}.chunk{i}")
            if not os.path.exists(chunk_path):
                print(f"Missing chunk {i} for {original_filename}")
                return False
            chunk_files.append(chunk_path)
        
        # Reassemble the file
        output_path = os.path.join(UPLOAD_DIR, original_filename)
        with open(output_path, 'wb') as output_file:
            for chunk_path in chunk_files:
                with open(chunk_path, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
        
        # Clean up chunk files
        for chunk_path in chunk_files:
            os.remove(chunk_path)
        
        # Remove from tracker
        if original_filename in chunk_tracker:
            del chunk_tracker[original_filename]
        
        print(f"Successfully reassembled {original_filename} from {total_chunks} chunks")
        return True
    except Exception as e:
        print(f"Error reassembling chunks for {original_filename}: {e}")
        return False

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
            <div style="margin-bottom: 15px;">
                <label for="chunk-count" style="display: block; margin-bottom: 5px; font-weight: bold;">Number of Chunks:</label>
                <input type="number" id="chunk-count" value="1" min="1" max="1000" placeholder="Number of chunks" style="width: 100%; max-width: 300px; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                <small style="color: #666; display: block; margin-top: 2px;">Split each file into this many chunks (1 = no chunking)</small>
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

            function getChunkCount() {
                const chunkInput = document.getElementById('chunk-count');
                return parseInt(chunkInput.value) || 1;
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
                  
                  if (!encryptionKey) {
                      statusDiv.innerHTML = 'Please enter an encryption key!';
                      statusDiv.style.color = '#dc3545';
                      return;
                  }
                  
                  dropArea.classList.add('uploading');
                  statusDiv.innerHTML = `Processing ${files.length} file(s) with ${chunkCount} chunk(s) each...`;
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
                              }
                              
                              updateFileStatus(i, 'Uploaded', '#28a745');
                          }
                      }
                      
                      statusDiv.innerHTML = 'All uploads completed!';
                      responseBox.innerHTML = "<pre>All files uploaded successfully</pre>";
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
            
            # Decrypt the file data
            decrypted_data = decrypt_file_data(file_data)
            if decrypted_data is None:
                self.send_error(500, "Failed to decrypt file")
                return
            
            if chunk_index is not None and total_chunks is not None:
                # Handle chunked upload
                chunk_index = int(chunk_index)
                total_chunks = int(total_chunks)
                
                # Initialize chunk tracker for this file
                if original_name not in chunk_tracker:
                    chunk_tracker[original_name] = {
                        'total_chunks': total_chunks,
                        'received_chunks': set()
                    }
                
                # Save chunk
                chunk_path = os.path.join(CHUNK_DIR, f"{original_name}.chunk{chunk_index}")
                with open(chunk_path, 'wb') as f:
                    f.write(decrypted_data)
                
                # Track received chunk
                chunk_tracker[original_name]['received_chunks'].add(chunk_index)
                
                print(f"Received chunk {chunk_index + 1}/{total_chunks} for {original_name}")
                
                # Check if all chunks received
                if len(chunk_tracker[original_name]['received_chunks']) == total_chunks:
                    if reassemble_chunks(original_name, total_chunks):
                        response_msg = f"File {original_name} successfully assembled from {total_chunks} chunks"
                    else:
                        response_msg = f"Failed to assemble {original_name}"
                        self.send_error(500, response_msg)
                        return
                else:
                    response_msg = f"Chunk {chunk_index + 1}/{total_chunks} received for {original_name}"
            else:
                # Handle regular upload (no chunking)
                out_path = os.path.join(UPLOAD_DIR, original_name)
                with open(out_path, 'wb') as f:
                    f.write(decrypted_data)
                
                response_msg = f"File {original_name} uploaded successfully"
            
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
