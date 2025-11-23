import os
import base64
import json
import atexit
import signal
import re
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
from e2b import Sandbox as E2BSandbox
from groq import Groq
import gdown
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Groq
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Setup directories
BASE_DIR = Path(__file__).parent.parent.absolute()
UPLOAD_DIR = BASE_DIR / "uploads"
CHARTS_DIR = BASE_DIR / "charts"
UPLOAD_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)

# Store active sandboxes per session
active_sandboxes = {}
uploaded_files = {}
# Store research sandboxes (MCP-enabled)
research_sandboxes = {}
# Store document collections per session (for semantic search)
document_collections = {}

def cleanup_all_sandboxes():
    """Cleanup all active sandboxes"""
    print("Cleaning up all sandboxes...")
    for session_id, sandbox in list(active_sandboxes.items()):
        try:
            # Try different cleanup methods
            if hasattr(sandbox, 'close'):
                sandbox.close()
            elif hasattr(sandbox, 'kill'):
                sandbox.kill()
            print(f"Closed sandbox for session: {session_id}")
        except Exception as e:
            print(f"Error closing sandbox {session_id}: {e}")
    active_sandboxes.clear()
    uploaded_files.clear()
    
    # Also cleanup research sandboxes
    print("Cleaning up research sandboxes...")
    for session_id, sandbox in list(research_sandboxes.items()):
        try:
            if hasattr(sandbox, 'kill'):
                sandbox.kill()
            elif hasattr(sandbox, 'close'):
                sandbox.close()
            print(f"Closed research sandbox for session: {session_id}")
        except Exception as e:
            print(f"Error closing research sandbox {session_id}: {e}")
    research_sandboxes.clear()

# Register cleanup handlers
atexit.register(cleanup_all_sandboxes)

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    cleanup_all_sandboxes()
    exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_or_create_sandbox(session_id):
    """Get existing sandbox or create new one"""
    if session_id not in active_sandboxes:
        active_sandboxes[session_id] = Sandbox.create()
    return active_sandboxes[session_id]

def cleanup_sandbox(session_id):
    """Close and remove sandbox"""
    if session_id in active_sandboxes:
        try:
            sandbox = active_sandboxes[session_id]
            # Try different cleanup methods
            if hasattr(sandbox, 'close'):
                sandbox.close()
            elif hasattr(sandbox, 'kill'):
                sandbox.kill()
            print(f"Closed sandbox for session: {session_id}")
        except Exception as e:
            print(f"Error closing sandbox {session_id}: {e}")
        del active_sandboxes[session_id]
    if session_id in uploaded_files:
        del uploaded_files[session_id]

def get_file_type(filename):
    """Determine file type from extension"""
    filename_lower = filename.lower()
    if filename_lower.endswith('.csv'):
        return 'csv'
    elif filename_lower.endswith('.xlsx'):
        return 'excel'
    elif filename_lower.endswith(('.pdf', '.docx', '.pptx', '.txt', '.md')):
        return 'document'
    return None

def extract_google_drive_file_id(url):
    """Extract file ID from Google Drive URL. Returns (file_id, is_folder) tuple."""
    # Check if it's a folder link
    if '/drive/folders/' in url or '/folders/' in url:
        folder_match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
        if folder_match:
            return folder_match.group(1), True
    
    # Pattern for Google Drive file sharing URLs
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'[a-zA-Z0-9_-]{25,}',  # Direct file ID (25+ chars)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1) if match.groups() else match.group(0)
            return file_id, False
    return None, False

def download_from_google_drive(url, output_path):
    """Download file from Google Drive using gdown with fallback to requests"""
    try:
        # Extract file ID and check if it's a folder
        file_id, is_folder = extract_google_drive_file_id(url)
        if not file_id:
            return None, "Could not extract file ID from Google Drive URL. Please make sure you're sharing a file (not a folder) and the link is public."
        
        if is_folder:
            return None, "Folder links are not supported. Please share the individual file directly. To download a file from a folder: 1) Open the file in Google Drive, 2) Click 'Share', 3) Set it to 'Anyone with the link', 4) Click 'Copy link' to get the file's direct link."
        
        print(f"Extracted file ID: {file_id}")
        
        # Method 1: Try gdown with proper parameters for public files
        try:
            print("Attempting download with gdown...")
            # Use fuzzy=True for public files and use_cookies=False to avoid cookie issues
            download_url = f"https://drive.google.com/uc?id={file_id}"
            gdown.download(
                download_url, 
                str(output_path), 
                quiet=False,
                fuzzy=True,  # Enable fuzzy matching for public files
                use_cookies=False  # Don't use cookies (better for server environments)
            )
            
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"Successfully downloaded with gdown: {output_path.stat().st_size} bytes")
                return str(output_path), None
            else:
                print("gdown download completed but file is empty or missing, trying requests...")
                raise Exception("gdown failed")
        except Exception as gdown_error:
            print(f"gdown failed: {str(gdown_error)}, trying requests fallback...")
            
            # Method 2: Fallback to requests library for direct download
            try:
                # Try different Google Drive download URL formats
                download_urls = [
                    f"https://drive.google.com/uc?export=download&id={file_id}",
                    f"https://drive.google.com/uc?id={file_id}&export=download",
                    f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}",  # With confirmation bypass
                ]
                
                for download_url in download_urls:
                    try:
                        print(f"Trying direct download URL: {download_url}")
                        response = requests.get(
                            download_url,
                            stream=True,
                            timeout=30,
                            allow_redirects=True,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            }
                        )
                        response.raise_for_status()
                        
                        # Check if we got a virus scan warning page (small HTML file)
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' in content_type:
                            # This might be a virus scan warning, try to extract the actual download link
                            html_content = response.text[:1000]  # First 1KB to check
                            if 'virus scan warning' in html_content.lower() or 'download anyway' in html_content.lower():
                                # Extract the confirm parameter from the HTML
                                confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html_content)
                                if confirm_match:
                                    confirm_token = confirm_match.group(1)
                                    download_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                                    print(f"Found confirmation token, retrying with: {download_url}")
                                    response = requests.get(
                                        download_url,
                                        stream=True,
                                        timeout=30,
                                        allow_redirects=True,
                                        headers={
                                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                        }
                                    )
                                    response.raise_for_status()
                        
                        # Download the file
                        total_size = 0
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    total_size += len(chunk)
                        
                        if output_path.exists() and output_path.stat().st_size > 0:
                            print(f"Successfully downloaded with requests: {output_path.stat().st_size} bytes")
                            return str(output_path), None
                        else:
                            print(f"Download completed but file is empty (size: {output_path.stat().st_size if output_path.exists() else 0})")
                            continue
                            
                    except requests.exceptions.RequestException as req_error:
                        print(f"Request failed for {download_url}: {str(req_error)}")
                        continue
                
                # If all methods failed
                return None, "All download methods failed. Possible reasons:\n1. The file may be too large (>100MB)\n2. The file requires authentication (make sure sharing is set to 'Anyone with the link')\n3. The link may be invalid or expired\n4. The file may have been deleted or moved\n\nPlease verify the file is publicly accessible and try again."
                
            except Exception as requests_error:
                return None, f"Both gdown and requests failed. Last error: {str(requests_error)}"
        
    except Exception as e:
        return None, f"Download failed: {str(e)}"

def ensure_semtools_installed(sandbox):
    """Ensure semtools is installed in the sandbox"""
    try:
        # Check if semtools is installed
        check_code = """
import subprocess
import shutil

# Check if semtools command exists
semtools_path = shutil.which('semtools')
if semtools_path:
    print(f"semtools found at: {semtools_path}")
else:
    print("not_found")
"""
        result = sandbox.run_code(check_code)
        
        needs_install = False
        if result.logs and result.logs.stdout:
            output = ''.join(result.logs.stdout).strip()
            if 'not_found' in output or not output or 'semtools found' not in output:
                needs_install = True
        
        if needs_install:
            # Install semtools via npm (preferred) or pip
            print("Installing semtools in sandbox...")
            install_code = """
import subprocess
import sys

# Try npm first (preferred method)
try:
    result = subprocess.run(['npm', 'install', '-g', '@llamaindex/semtools'], 
                           capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        print("semtools installed via npm")
    else:
        raise Exception("npm install failed")
except Exception as npm_error:
    print(f"npm install failed: {npm_error}, trying pip...")
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'semtools'], 
                               capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            print("semtools installed via pip")
        else:
            print(f"pip install also failed: {result.stderr}")
    except Exception as pip_error:
        print(f"pip install failed: {pip_error}")

# Verify installation
import shutil
semtools_path = shutil.which('semtools')
if semtools_path:
    print(f"semtools successfully installed at: {semtools_path}")
else:
    print("WARNING: semtools installation may have failed")
"""
            install_result = sandbox.run_code(install_code)
            if install_result.logs and install_result.logs.stdout:
                print(f"Semtools installation output: {''.join(install_result.logs.stdout)}")
        else:
            print("Semtools already installed")
        return True
    except Exception as e:
        print(f"Error checking/installing semtools: {e}")
        import traceback
        traceback.print_exc()
        return False

def parse_documents_in_sandbox(sandbox, documents_dir="/home/user/documents"):
    """Parse documents in sandbox - extract text from PDFs, DOCX, etc. for LLM processing"""
    try:
        # Parse documents to extract text content
        # This is necessary because Groq/Qwen3 only accepts text, not binary files
        parse_code = f"""
import subprocess
import os
import glob
import sys

# Find all document files
doc_patterns = ['{documents_dir}/*.pdf', '{documents_dir}/*.docx', '{documents_dir}/*.pptx', '{documents_dir}/*.txt', '{documents_dir}/*.md']
files = []
for pattern in doc_patterns:
    files.extend(glob.glob(pattern))

parsed_files = []

for file_path in files:
    file_ext = os.path.splitext(file_path)[1].lower()
    output_path = os.path.splitext(file_path)[0] + '.txt'
    
    try:
        if file_ext == '.pdf':
            # Try PyPDF2 or pdfplumber for PDF extraction
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text_content = []
                    for page in pdf_reader.pages:
                        text_content.append(page.extract_text())
                    with open(output_path, 'w', encoding='utf-8') as out:
                        out.write('\\n\\n'.join(text_content))
                    parsed_files.append(output_path)
                    print(f"Parsed PDF: {{file_path}} -> {{output_path}}")
            except ImportError:
                # Try pdfplumber
                try:
                    import pdfplumber
                    text_content = []
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            text_content.append(page.extract_text() or '')
                    with open(output_path, 'w', encoding='utf-8') as out:
                        out.write('\\n\\n'.join(text_content))
                    parsed_files.append(output_path)
                    print(f"Parsed PDF: {{file_path}} -> {{output_path}}")
                except ImportError:
                    # Fallback: try semtools parse if available
                    try:
                        result = subprocess.run(['semtools', 'parse', file_path], 
                                              capture_output=True, text=True, timeout=60)
                        if result.returncode == 0:
                            # semtools outputs to stdout or creates .md file
                            md_path = os.path.splitext(file_path)[0] + '.md'
                            if os.path.exists(md_path):
                                parsed_files.append(md_path)
                                print(f"Parsed PDF with semtools: {{file_path}} -> {{md_path}}")
                    except:
                        print(f"Warning: Could not parse PDF {{file_path}}. Install PyPDF2 or pdfplumber: pip install PyPDF2 pdfplumber")
        
        elif file_ext == '.docx':
            try:
                import docx
                doc = docx.Document(file_path)
                text_content = '\\n'.join([para.text for para in doc.paragraphs])
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(text_content)
                parsed_files.append(output_path)
                print(f"Parsed DOCX: {{file_path}} -> {{output_path}}")
            except ImportError:
                print(f"Warning: Could not parse DOCX {{file_path}}. Install python-docx: pip install python-docx")
        
        elif file_ext in ['.txt', '.md']:
            # Already text files, no parsing needed
            parsed_files.append(file_path)
            print(f"Text file (no parsing needed): {{file_path}}")
    
    except Exception as e:
        print(f"Error parsing {{file_path}}: {{str(e)}}")

if parsed_files:
    print(f"Successfully parsed {{len(parsed_files)}} files")
else:
    print("No files were parsed (may need to install parsing libraries)")
"""
        result = sandbox.run_code(parse_code)
        return result
    except Exception as e:
        print(f"Error parsing documents: {e}")
        import traceback
        traceback.print_exc()
        return None

def semantic_search_documents(sandbox, query, documents_dir="/home/user/documents", max_distance=0.5, top_k=5):
    """Perform agentic search to find relevant documents, then extract text from PDFs using LlamaParse"""
    try:
        # Ensure semtools is installed
        ensure_semtools_installed(sandbox)
        
        # Get LlamaParse API key
        llama_api_key = os.getenv('LLAMA_CLOUD_API_KEY')
        has_llamaparse = bool(llama_api_key)
        
        # Escape query for shell
        escaped_query = query.replace("'", "'\"'\"'")
        
        # Step 1: Agentic search to find relevant documents
        # Use semtools search to find which documents/files are relevant to the query
        search_code = f"""
import subprocess
import os
import json
import glob
import shlex

# Find all available documents (PDFs, DOCX, text files, etc.)
all_documents = []
for pattern in ['*.pdf', '*.docx', '*.pptx', '*.txt', '*.md', '*.markdown']:
    files = glob.glob(os.path.join('{documents_dir}', '**', pattern), recursive=True)
    all_documents.extend(files)

# Also check for already parsed text files
parsed_text_files = []
for pattern in ['*.txt', '*.md', '*.markdown']:
    files = glob.glob(os.path.join('{documents_dir}', '**', pattern), recursive=True)
    parsed_text_files.extend(files)

print(f"Found {{len(all_documents)}} total documents, {{len(parsed_text_files)}} already parsed")

# If we have parsed text files, use semtools search on them first
relevant_files = []
if parsed_text_files:
    try:
        files_str = ' '.join([shlex.quote(f) for f in parsed_text_files[:20]])
        query_escaped = shlex.quote('{escaped_query}')
        cmd = f"semtools search {query_escaped} {files_str} --max-distance {max_distance} --top-k {top_k} --n-lines 2"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd='/home/user')
        if result.returncode == 0 and result.stdout:
            # Extract file paths from search results
            output_lines = result.stdout.split('\\n')
            for line in output_lines:
                # Look for file paths in the output
                if '{documents_dir}' in line or any(ext in line for ext in ['.txt', '.md', '.pdf', '.docx']):
                    # Try to extract file path
                    for doc in all_documents + parsed_text_files:
                        if os.path.basename(doc) in line or doc in line:
                            if doc not in relevant_files:
                                relevant_files.append(doc)
            print(f"Agentic search found {{len(relevant_files)}} relevant files")
            if result.stdout:
                print("Search results preview:")
                print(result.stdout[:1000])  # Preview of search results
    except Exception as e:
        print(f"Semtools search error: {{str(e)}}")

# If no relevant files found, use all documents
if not relevant_files:
    relevant_files = all_documents[:10]  # Limit to first 10

# Identify PDFs that need parsing
pdfs_to_parse = [f for f in relevant_files if f.lower().endswith('.pdf')]
print(f"Found {{len(pdfs_to_parse)}} PDFs that may need parsing")

# Output results as JSON for processing
results = {{
    'relevant_files': relevant_files,
    'pdfs_to_parse': pdfs_to_parse,
    'parsed_text_files': parsed_text_files,
    'all_documents': all_documents
}}
print("\\n=== SEARCH RESULTS ===")
print(json.dumps(results, indent=2))
"""
        result = sandbox.run_code(search_code)
        
        # Parse the JSON output to get relevant files
        relevant_files = []
        pdfs_to_parse = []
        search_preview = ""
        
        if result.logs and result.logs.stdout:
            output = ''.join(result.logs.stdout)
            search_preview = output
            
            # Try to extract JSON from output
            try:
                # Find JSON in output
                json_start = output.find('{')
                json_end = output.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = output[json_start:json_end]
                    search_data = json.loads(json_str)
                    relevant_files = search_data.get('relevant_files', [])
                    pdfs_to_parse = search_data.get('pdfs_to_parse', [])
            except:
                pass
        
        # Step 2: Use LlamaParse to extract text from PDFs if available
        extracted_texts = {}
        if pdfs_to_parse and has_llamaparse:
            print(f"Using LlamaParse to extract text from {len(pdfs_to_parse)} PDFs...")
            extracted_texts = parse_pdfs_with_llamaparse(sandbox, pdfs_to_parse, llama_api_key)
        elif pdfs_to_parse:
            print(f"LlamaParse not available, using fallback PDF parsing for {len(pdfs_to_parse)} PDFs...")
            extracted_texts = parse_pdfs_fallback(sandbox, pdfs_to_parse)
        
        # Step 3: Combine search results with extracted PDF text
        final_results = search_preview
        
        if extracted_texts:
            final_results += "\n\n=== EXTRACTED PDF CONTENT ===\n"
            for pdf_path, text_content in extracted_texts.items():
                if text_content:
                    final_results += f"\n--- Content from {os.path.basename(pdf_path)} ---\n"
                    final_results += text_content[:2000]  # Limit each PDF to 2000 chars
                    final_results += "\n"
        
        return final_results if final_results else None
        
    except Exception as e:
        print(f"Error in semantic search: {e}")
        import traceback
        traceback.print_exc()
        return None

def parse_pdfs_with_llamaparse(sandbox, pdf_paths, api_key):
    """Use LlamaParse via semtools to extract text from PDFs"""
    extracted_texts = {}
    
    try:
        # Set up LlamaParse API key in sandbox environment
        setup_code = f"""
import os
os.environ['LLAMA_CLOUD_API_KEY'] = '{api_key}'
print("LlamaParse API key configured")
"""
        sandbox.run_code(setup_code)
        
        # Parse each PDF using semtools parse (which uses LlamaParse)
        for pdf_path in pdf_paths[:5]:  # Limit to 5 PDFs
            try:
                parse_code = f"""
import subprocess
import os
import json

pdf_path = '{pdf_path}'
output_path = os.path.splitext(pdf_path)[0] + '_parsed.md'

# Use semtools parse with LlamaParse backend
try:
    # Set API key
    os.environ['LLAMA_CLOUD_API_KEY'] = '{api_key}'
    
    # Run semtools parse
    result = subprocess.run(
        ['semtools', 'parse', pdf_path],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy()
    )
    
    if result.returncode == 0:
        # semtools parse outputs markdown to stdout or creates a file
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            # Check if output is in stdout
            content = result.stdout if result.stdout else ""
        
        if content:
            print(f"SUCCESS: Parsed {{pdf_path}}")
            print(f"CONTENT_LENGTH: {{len(content)}}")
            print(f"CONTENT_PREVIEW: {{content[:500]}}")
        else:
            print(f"WARNING: No content extracted from {{pdf_path}}")
    else:
        print(f"ERROR: semtools parse failed: {{result.stderr}}")
except Exception as e:
    print(f"ERROR parsing {{pdf_path}}: {{str(e)}}")
"""
                result = sandbox.run_code(parse_code)
                
                # Extract content from result
                if result.logs and result.logs.stdout:
                    output = ''.join(result.logs.stdout)
                    # Try to extract content preview
                    if 'CONTENT_PREVIEW:' in output:
                        content_start = output.find('CONTENT_PREVIEW:') + len('CONTENT_PREVIEW:')
                        content = output[content_start:].strip()
                        if content:
                            extracted_texts[pdf_path] = content
                    elif 'SUCCESS' in output:
                        # Content might be in a file, try to read it
                        md_path = pdf_path.replace('.pdf', '_parsed.md')
                        read_code = f"""
import os
md_path = '{md_path}'
if os.path.exists(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        print(f.read()[:5000])
else:
    print("Parsed file not found")
"""
                        read_result = sandbox.run_code(read_code)
                        if read_result.logs and read_result.logs.stdout:
                            content = ''.join(read_result.logs.stdout).strip()
                            if content and content != "Parsed file not found":
                                extracted_texts[pdf_path] = content
                
            except Exception as e:
                print(f"Error parsing PDF {pdf_path} with LlamaParse: {e}")
                continue
        
    except Exception as e:
        print(f"Error in LlamaParse setup: {e}")
    
    return extracted_texts

def parse_pdfs_fallback(sandbox, pdf_paths):
    """Fallback PDF parsing using PyPDF2 or pdfplumber"""
    extracted_texts = {}
    
    parse_code = f"""
import os
import glob

pdf_paths = {json.dumps(pdf_paths[:5])}  # Limit to 5 PDFs

for pdf_path in pdf_paths:
    if not os.path.exists(pdf_path):
        continue
    
    output_path = os.path.splitext(pdf_path)[0] + '_parsed.txt'
    
    try:
        # Try PyPDF2 first
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text_content = []
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
                content = '\\n\\n'.join(text_content)
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(content)
                print(f"SUCCESS: Parsed {{pdf_path}} with PyPDF2")
                print(f"CONTENT_PREVIEW: {{content[:500]}}")
        except ImportError:
            # Try pdfplumber
            try:
                import pdfplumber
                text_content = []
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text_content.append(page.extract_text() or '')
                content = '\\n\\n'.join(text_content)
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(content)
                print(f"SUCCESS: Parsed {{pdf_path}} with pdfplumber")
                print(f"CONTENT_PREVIEW: {{content[:500]}}")
            except ImportError:
                print(f"ERROR: No PDF parsing libraries available for {{pdf_path}}")
    except Exception as e:
        print(f"ERROR parsing {{pdf_path}}: {{str(e)}}")
"""
    result = sandbox.run_code(parse_code)
    
    # Extract content from results
    if result.logs and result.logs.stdout:
        output = ''.join(result.logs.stdout)
        for pdf_path in pdf_paths[:5]:
            if f'SUCCESS: Parsed {pdf_path}' in output:
                # Try to read the parsed file
                txt_path = pdf_path.replace('.pdf', '_parsed.txt')
                read_code = f"""
import os
txt_path = '{txt_path}'
if os.path.exists(txt_path):
    with open(txt_path, 'r', encoding='utf-8') as f:
        print(f.read()[:5000])
"""
                read_result = sandbox.run_code(read_code)
                if read_result.logs and read_result.logs.stdout:
                    content = ''.join(read_result.logs.stdout).strip()
                    if content:
                        extracted_texts[pdf_path] = content
    
    return extracted_texts

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload CSV, XLS, or Excel file to sandbox"""
    try:
        print(f"Upload request received")
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', 'default')
        print(f"Uploading file: {file.filename}, session_id: {session_id}")
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        file_type = get_file_type(file.filename)
        if not file_type:
            return jsonify({'error': 'Only CSV and Excel (.xlsx) files are allowed'}), 400
        
        # Save file locally
        print("Saving file locally...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        filepath = UPLOAD_DIR / filename
        file.save(filepath)
        print(f"File saved to: {filepath}")
        
        # Upload to sandbox
        print(f"Creating/getting sandbox for session: {session_id}")
        sbx = get_or_create_sandbox(session_id)
        print("Sandbox ready, uploading file to sandbox...")
        with open(filepath, 'rb') as f:
            sandbox_path = sbx.files.write(f"/home/user/{file.filename}", f)
        print(f"File uploaded to sandbox: {sandbox_path.path}")
        
        # Analyze file to get column info (optimized for large files)
        print(f"Running analysis code to extract column info for {file_type} file...")
        
        # Generate appropriate analysis code based on file type
        if file_type == 'csv':
            analysis_code = f"""
import pandas as pd
import json
import numpy as np

# Read only first few rows to get structure quickly
df = pd.read_csv("{sandbox_path.path}", nrows=100)
# Get row count efficiently
try:
    with open("{sandbox_path.path}", 'r') as f:
        total_rows = sum(1 for line in f) - 1  # Subtract header
except:
    total_rows = len(df)

# Replace NaN values with None for JSON serialization
df_sample = df.head(3)
# Convert NaN/NaT to None for JSON serialization
df_sample = df_sample.where(pd.notna(df_sample), None)
sample_data = df_sample.to_dict(orient='records')

# Convert any remaining NaN/NaT values to None in the sample data
# This handles edge cases where fillna might not catch everything
def clean_nan(obj):
    if isinstance(obj, dict):
        return dict((k, clean_nan(v)) for k, v in obj.items())
    elif isinstance(obj, list):
        return [clean_nan(item) for item in obj]
    elif pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
        return None
    else:
        return obj

sample_data = [clean_nan(record) for record in sample_data]

columns_info = {{
    'columns': list(df.columns),
    'shape': [total_rows, len(df.columns)],
    'dtypes': df.dtypes.astype(str).to_dict(),
    'sample': sample_data
}}
print(json.dumps(columns_info))
"""
        else:  # excel (.xlsx) - simplified for single sheet
            analysis_code = f"""
import pandas as pd
import json
import numpy as np

file_path = "{sandbox_path.path}"

try:
    # Read only first few rows to get structure quickly (single sheet assumed)
    df = pd.read_excel(file_path, engine='openpyxl', nrows=100)
        # Get row count efficiently
        try:
            # For Excel files, read the full sheet to get accurate row count
        df_full = pd.read_excel(file_path, engine='openpyxl')
            total_rows = len(df_full)
        except:
            total_rows = len(df)
        
        # Replace NaN values with None for JSON serialization
    df_sample = df.head(3)
    # Convert NaN/NaT to None for JSON serialization
    df_sample = df_sample.where(pd.notna(df_sample), None)
        sample_data = df_sample.to_dict(orient='records')
        
        # Convert any remaining NaN/NaT values to None in the sample data
        def clean_nan(obj):
            if isinstance(obj, dict):
                return dict((k, clean_nan(v)) for k, v in obj.items())
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif pd.isna(obj) or (isinstance(obj, float) and np.isnan(obj)):
                return None
            else:
                return obj
        
        sample_data = [clean_nan(record) for record in sample_data]
        
    columns_info = {{
            'columns': list(df.columns),
            'shape': [total_rows, len(df.columns)],
            'dtypes': df.dtypes.astype(str).to_dict(),
            'sample': sample_data
        }}
    except Exception as e:
    # If Excel reading fails, return error info
    columns_info = {{
            'columns': [],
            'shape': [0, 0],
            'dtypes': {{}},
            'sample': [],
        'error': f'Failed to read Excel file: {{str(e)}}'
    }}

print(json.dumps(columns_info))
"""
        
        print("Executing analysis code in sandbox...")
        try:
            result = sbx.run_code(analysis_code)
        except Exception as e:
            print(f"Error executing analysis code: {e}")
            # Fallback: return basic structure
            return jsonify({
                'success': True,
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'columns_info': {
                    'columns': [],
                    'shape': [0, 0],
                    'dtypes': {},
                    'sample': []
                },
                'session_id': session_id,
                'warning': f'Could not analyze {file_type.upper()} file structure automatically'
            })
        print(f"Analysis code executed. Results: {len(result.results) if result.results else 0} results")
        
        if result.error:
            print(f"Analysis code error: {result.error.name}: {result.error.value}")
            # Return basic structure even if analysis fails
            columns_info = {
                'columns': [],
                'shape': [0, 0],
                'dtypes': {},
                'sample': []
            }
            
            # Store file info even with error
            if session_id not in uploaded_files:
                uploaded_files[session_id] = []
            
            file_info = {
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'local_path': str(filepath),
                'file_type': file_type,
                'columns_info': columns_info
            }
            uploaded_files[session_id].append(file_info)
            
            return jsonify({
                'success': True,
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'columns_info': columns_info,
                'session_id': session_id,
                'warning': f'Could not analyze {file_type.upper()} file structure automatically'
            })
        else:
            # Extract the actual dictionary value from the result
            columns_info = {}
            import ast
            
            # First try to get from stdout logs (where print() output goes)
            if hasattr(result, 'logs') and hasattr(result.logs, 'stdout') and result.logs.stdout:
                stdout_text = ''.join(result.logs.stdout).strip()
                print(f"Captured stdout: {stdout_text[:300]}")
                if stdout_text:
                    try:
                        # Try to parse as JSON first (since we're using json.dumps now)
                        import json
                        columns_info = json.loads(stdout_text)
                        print("Successfully parsed columns_info from JSON stdout")
                    except (ValueError, json.JSONDecodeError):
                        try:
                            # Fallback: Try to find the dict in stdout
                            if '{' in stdout_text:
                                # Extract the dict portion
                                start = stdout_text.find('{')
                                end = stdout_text.rfind('}') + 1
                                if start >= 0 and end > start:
                                    dict_str = stdout_text[start:end]
                                    columns_info = ast.literal_eval(dict_str)
                                    print("Successfully parsed columns_info from stdout")
                        except (ValueError, SyntaxError) as e:
                            print(f"Failed to parse stdout: {e}")
            
            # If not found in stdout, try results
            if not columns_info and result.results and len(result.results) > 0:
                try:
                    # Get the text representation of the result (e2b returns dict as string)
                    result_obj = result.results[0]
                    if hasattr(result_obj, 'text') and result_obj.text:
                        # Parse the string representation of the dict
                        result_text = result_obj.text.strip()
                        # Remove any leading/trailing whitespace and parse
                        columns_info = ast.literal_eval(result_text)
                        print("Successfully parsed columns_info from results")
                    else:
                        # Fallback: try to convert to string and parse
                        result_text = str(result_obj).strip()
                        if result_text.startswith('{'):
                            columns_info = ast.literal_eval(result_text)
                            print("Successfully parsed columns_info from string conversion")
                except (ValueError, SyntaxError, AttributeError) as e:
                    print(f"Failed to parse results: {e}")
            
            # If still no columns_info, return empty structure
            if not columns_info:
                print("Warning: Could not extract columns_info, using empty structure")
                columns_info = {
                    'columns': [],
                    'shape': (0, 0),
                    'dtypes': {},
                    'sample': []
                }
        
            # Store files as a list to support multiple uploads
            if session_id not in uploaded_files:
                uploaded_files[session_id] = []
            
            file_info = {
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'local_path': str(filepath),
                'file_type': file_type,
                'columns_info': columns_info
            }
            uploaded_files[session_id].append(file_info)
            
            print(f"Upload completed successfully. Columns: {len(columns_info.get('columns', []))}")
            return jsonify({
                'success': True,
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'columns_info': columns_info,
                'session_id': session_id  # Return session_id so frontend can use it
            })
    
    except Exception as e:
        print(f"Error in upload_file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-google-drive', methods=['POST'])
def download_google_drive():
    """Download files from Google Drive link to e2b sandbox"""
    try:
        data = request.json
        google_drive_url = data.get('url', '')
        session_id = data.get('session_id', 'default')
        
        if not google_drive_url:
            return jsonify({'error': 'No Google Drive URL provided'}), 400
        
        print(f"Downloading from Google Drive: {google_drive_url}, session_id: {session_id}")
        
        # Get or create sandbox
        sbx = get_or_create_sandbox(session_id)
        
        # Create documents directory in sandbox
        documents_dir = "/home/user/documents"
        mkdir_code = f"mkdir -p {documents_dir}"
        sbx.run_code(mkdir_code)
        
        # Download file locally first
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"gdrive_download_{timestamp}"
        temp_path = UPLOAD_DIR / temp_filename
        
        file_path, error = download_from_google_drive(google_drive_url, temp_path)
        if error:
            return jsonify({'error': error}), 400
        
        # Determine actual filename from downloaded file
        downloaded_file = Path(file_path)
        if not downloaded_file.exists():
            return jsonify({'error': 'Downloaded file not found'}), 500
        
        # Try to get original filename from Google Drive (if possible)
        # For now, use a generic name based on extension
        file_extension = downloaded_file.suffix if downloaded_file.suffix else '.bin'
        final_filename = f"document_{timestamp}{file_extension}"
        
        # Upload to sandbox
        with open(downloaded_file, 'rb') as f:
            sandbox_path = sbx.files.write(f"{documents_dir}/{final_filename}", f)
        
        print(f"File uploaded to sandbox: {sandbox_path.path}")
        
        # Initialize document collection for this session
        if session_id not in document_collections:
            document_collections[session_id] = []
        
        document_collections[session_id].append({
            'filename': final_filename,
            'sandbox_path': sandbox_path.path,
            'local_path': str(downloaded_file),
            'url': google_drive_url
        })
        
        # Note: Documents will be parsed on-demand during semantic search
        # This allows us to use agentic search first, then parse only relevant PDFs with LlamaParse
        print(f"Document {final_filename} ready for agentic search")
        
        # Clean up local file
        try:
            downloaded_file.unlink()
        except:
            pass
        
        return jsonify({
            'success': True,
            'filename': final_filename,
            'sandbox_path': sandbox_path.path,
            'session_id': session_id,
            'message': f'File downloaded and uploaded to sandbox successfully'
        })
    
    except Exception as e:
        print(f"Error in download_google_drive: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def select_relevant_csvs(query, csv_files_info):
    """Use LLM to select which CSV file(s) are most relevant to the query"""
    try:
        if len(csv_files_info) == 0:
            return []
        if len(csv_files_info) == 1:
            return [0]  # Return index of the single file
        
        # Build file descriptions for LLM
        files_description = ""
        for idx, file_info in enumerate(csv_files_info):
            filename = file_info.get('filename', 'unknown')
            columns = file_info.get('columns', [])
            file_type = file_info.get('file_type', 'csv')
            shape = file_info.get('columns_info', {}).get('shape', [0, 0])
            files_description += f"\n{idx}. {filename} ({file_type.upper()})\n"
            files_description += f"   Columns: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''}\n"
            files_description += f"   Shape: {shape[0]} rows x {shape[1]} columns\n"
        
        prompt = f"""Given the user's query and multiple CSV/Excel files, determine which file(s) are most relevant.

User query: "{query}"

Available files:
{files_description}

Respond with ONLY a comma-separated list of file numbers (0-indexed) that are relevant to the query.
For example: "0" for file 0, "0,2" for files 0 and 2, or "all" if all files are needed.
If the query doesn't clearly relate to any specific file, respond with "all"."""
        
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a file selection assistant. Analyze queries and select the most relevant CSV/Excel files. Respond with only comma-separated numbers or 'all'."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        selection = response.choices[0].message.content.strip().lower()
        
        # Parse selection
        if selection == 'all':
            return list(range(len(csv_files_info)))
        
        # Parse comma-separated indices
        try:
            indices = [int(x.strip()) for x in selection.split(',')]
            # Validate indices
            valid_indices = [idx for idx in indices if 0 <= idx < len(csv_files_info)]
            return valid_indices if valid_indices else list(range(len(csv_files_info)))
        except:
            # If parsing fails, return all files
            return list(range(len(csv_files_info)))
            
    except Exception as e:
        print(f"Error selecting relevant CSVs: {e}")
        # Fallback: return all files
        return list(range(len(csv_files_info)))

def determine_query_type_with_llm(message, has_csv_data=False, csv_columns=None, has_documents=False):
    """Use LLM to determine if query needs CSV analysis, web search, document search, or combination"""
    try:
        # Simple, clear prompt for Groq to detect intent
        prompt = f"""Analyze this user query and determine what action is needed:

User query: "{message}"

Available actions:
1. csv_only - Query is EXPLICITLY asking to analyze CSV data (e.g., "show statistics", "analyze the data", "what's in the CSV")
2. web_search_only - Query asks for research, information, facts, news, or anything NOT in uploaded data (e.g., "research X", "find information about Y", "what is Z", "tell me about")
3. document_search - Query asks about content in uploaded documents (e.g., "what does the document say", "summarize the document", "find information in the files")
4. both - Query EXPLICITLY needs both CSV analysis AND web research
5. needs_csv - Query EXPLICITLY asks to analyze a CSV file but none exists

"""
        
        if has_documents:
            prompt += f"""Documents ARE available in the sandbox.

IMPORTANT: ONLY use document_search if the query EXPLICITLY mentions documents, files, uploaded content, or asks questions like "what does the document say", "summarize the file", "what's in the uploaded document". 
For general questions, research queries, or questions not explicitly about document content, use web_search_only.
"""
        
        if has_csv_data and csv_columns:
            prompt += f"""A CSV file IS available with columns: {', '.join(csv_columns)}

IMPORTANT: If the query asks to "research", "search", "find information", or asks about topics/companies/facts NOT in the CSV, use web_search_only.
Only use csv_only if the query is clearly about analyzing the uploaded CSV data.
"""
        else:
            prompt += """NO CSV file is uploaded.

IMPORTANT: If the user asks ANY question (research, information, facts, companies, news, etc.) and no documents are available, respond with web_search_only.
Only use needs_csv if the query EXPLICITLY asks to analyze a CSV file that doesn't exist.
"""
        
        prompt += """
Respond with ONLY one word: csv_only, web_search_only, document_search, both, or needs_csv"""

        # Call Groq to determine intent
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a query router. Analyze the user's query and respond with ONLY one word: csv_only, web_search_only, document_search, both, or needs_csv. Use document_search ONLY if the query explicitly mentions documents/files. For general questions or research, use web_search_only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=20
        )
        
        query_type = response.choices[0].message.content.strip().lower()
        
        # Extract just the type if LLM added extra text
        valid_types = ['csv_only', 'web_search_only', 'document_search', 'both', 'needs_csv']
        for valid_type in valid_types:
            if valid_type in query_type:
                query_type = valid_type
                break
        
        # Safety override: Only use document_search if documents exist AND query explicitly mentions documents/files
        if query_type == 'document_search' and not has_documents:
            print(f"Safety override: document_search requested but no documents available, defaulting to web_search_only")
            query_type = 'web_search_only'
        
        # Safety override: if documents available and query explicitly mentions documents, use document_search
        if has_documents:
            document_keywords = ['document', 'file', 'uploaded', 'downloaded', 'what does it say', 'summarize the document', 'in the document', 'from the file', 'in the file', 'what\'s in the document']
            message_lower = message.lower()
            # Only override if query explicitly mentions documents/files
            if any(keyword in message_lower for keyword in document_keywords):
                if query_type not in ['document_search', 'both']:
                    print(f"Safety override: forcing document_search for explicit document-related query")
                    query_type = 'document_search'
        
        # Safety override: if no CSV and no documents, and query contains research keywords, force web_search_only
        if not has_csv_data and not has_documents:
            research_keywords = ['research', 'search', 'find', 'look up', 'tell me', 'what is', 'who is', 'information about']
            message_lower = message.lower()
            if any(keyword in message_lower for keyword in research_keywords):
                if query_type != 'web_search_only':
                    print(f"Safety override: forcing web_search_only for research query without CSV or documents")
                    query_type = 'web_search_only'
        
        # Safety override: if query_type is needs_csv but no CSV, default based on available resources
        if query_type == 'needs_csv' and not has_csv_data:
            if has_documents:
                print(f"Safety override: needs_csv without CSV, defaulting to document_search")
                query_type = 'document_search'
            else:
                print(f"Safety override: needs_csv without CSV, defaulting to web_search_only")
                query_type = 'web_search_only'
        
        # Final fallback: if document_search but no documents, use web_search_only
        if query_type == 'document_search' and not has_documents:
            print(f"Final safety check: document_search without documents, using web_search_only")
            query_type = 'web_search_only'
        
        return query_type if query_type in valid_types else ('web_search_only' if not has_csv_data and not has_documents else ('document_search' if has_documents else 'csv_only'))
            
    except Exception as e:
        print(f"Error in LLM-based query type determination: {e}")
        # Fallback: if no CSV, always allow web search
        if not has_csv_data:
            return 'web_search_only'
        # If CSV exists, check for research keywords
        research_keywords = ['research', 'search', 'find', 'look up', 'tell me', 'what is']
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in research_keywords):
            return 'web_search_only'
        return 'csv_only'

def perform_web_research(query, research_session_id):
    """Perform web research using E2B MCP sandbox"""
    try:
        exa_api_key = os.getenv('EXA_API_KEY')
        if not exa_api_key:
            return None, "EXA_API_KEY not configured"
        
        # Get or create research sandbox
        if research_session_id not in research_sandboxes:
            try:
                research_sandbox = E2BSandbox.create(
                    mcp={
                        "exa": {
                            "apiKey": exa_api_key
                        }
                    }
                )
                research_sandboxes[research_session_id] = research_sandbox
            except Exception as e:
                return None, f"Failed to create research sandbox: {str(e)}"
        else:
            research_sandbox = research_sandboxes[research_session_id]
        
        # Get MCP URL and token
        try:
            if hasattr(research_sandbox, 'get_mcp_url'):
                mcp_url = research_sandbox.get_mcp_url()
            elif hasattr(research_sandbox, 'getMcpUrl'):
                mcp_url = research_sandbox.getMcpUrl()
            else:
                mcp_url = getattr(research_sandbox, 'mcp_url', None)
            
            if hasattr(research_sandbox, 'get_mcp_token'):
                mcp_token = research_sandbox.get_mcp_token()
            elif hasattr(research_sandbox, 'getMcpToken'):
                mcp_token = research_sandbox.getMcpToken()
            else:
                mcp_token = getattr(research_sandbox, 'mcp_token', None)
            
            if not mcp_url or not mcp_token:
                return None, "Could not retrieve MCP configuration"
        except Exception as e:
            return None, f"Error getting MCP configuration: {str(e)}"
        
        research_prompt = f"""{query}

Use Exa to search for recent and relevant information to answer this question comprehensively. 
Provide a detailed summary with sources and key findings."""
        
        print(f"Calling Groq with MCP tools for web research...")
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a research assistant. Use the available tools to search the web and provide comprehensive, well-sourced answers."
                },
                {
                    "role": "user",
                    "content": research_prompt
                }
            ],
            tools=[
                {
                    "type": "mcp",
                    "server_label": "e2b-mcp-gateway",
                    "server_url": mcp_url,
                    "headers": {
                        "Authorization": f"Bearer {mcp_token}"
                    }
                }
            ],
            temperature=0.7,
            max_tokens=2048
        )
        
        research_result = response.choices[0].message.content
        if not research_result or len(research_result.strip()) == 0:
            return None, "Web research returned empty result"
        print(f"Web research completed successfully ({len(research_result)} chars)")
        return research_result, None
        
    except Exception as e:
        error_msg = f"Research failed: {str(e)}"
        print(f"Web research error: {error_msg}")
        import traceback
        traceback.print_exc()
        return None, error_msg

@app.route('/api/chat', methods=['POST'])
def chat():
    """Intelligent chat endpoint that routes to CSV analysis, web search, or both"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        print(f"Chat request - session_id: {session_id}, message: {message[:100]}")
        
        # Check if data files are available
        has_csv = session_id in uploaded_files and len(uploaded_files[session_id]) > 0
        csv_files = uploaded_files.get(session_id, []) if has_csv else []
        csv_columns = []
        all_csv_info = []
        
        if has_csv:
            # Collect all CSV columns and file info
            for file_info in csv_files:
                columns = file_info.get('columns_info', {}).get('columns', [])
                csv_columns.extend(columns)
                all_csv_info.append({
                    'filename': file_info.get('filename'),
                    'columns': columns,
                    'file_type': file_info.get('file_type'),
                    'sandbox_path': file_info.get('sandbox_path'),
                    'columns_info': file_info.get('columns_info', {})
                })
        
        # Check if documents are available
        has_documents = session_id in document_collections and len(document_collections[session_id]) > 0
        
        # Use LLM to determine what type of query this is and which CSV(s) to use
        query_type = determine_query_type_with_llm(message, has_csv_data=has_csv, csv_columns=csv_columns, has_documents=has_documents)
        
        # If multiple CSVs, let LLM select which one(s) to use
        selected_files = []
        if has_csv and len(csv_files) > 1 and query_type in ['csv_only', 'both']:
            selected_indices = select_relevant_csvs(message, all_csv_info)
            selected_files = [csv_files[idx] for idx in selected_indices]
            print(f"LLM selected {len(selected_files)} CSV file(s) out of {len(csv_files)} available")
        elif has_csv:
            selected_files = csv_files  # Use all files if only one or if not csv_only/both
        print(f"Query type determined by LLM: {query_type}")
        
        # Handle different query types
        # If needs_csv but no CSV, default based on available resources
        if query_type == 'needs_csv' and not has_csv:
            if has_documents:
                print(f"Overriding needs_csv to document_search (documents available)")
                query_type = 'document_search'
            else:
                print(f"Overriding needs_csv to web_search_only (no CSV or documents, allowing web search)")
            query_type = 'web_search_only'
        
        # Perform document search if needed
        document_search_result = None
        document_search_error = None
        if query_type == 'document_search':
            print(f"Performing document search for query: {message[:100]}")
            if not has_documents:
                # Fallback to web search if documents aren't available
                print(f"No documents available for document_search, falling back to web_search_only")
                query_type = 'web_search_only'
            
            try:
                sbx = get_or_create_sandbox(session_id)
                document_search_result = semantic_search_documents(sbx, message, max_distance=0.5, top_k=5)
                
                if not document_search_result:
                    document_search_error = "Document search returned no results"
                    print(f"Document search error: {document_search_error}")
                else:
                    # Generate answer based on search results
                    print(f"Document search completed. Generating answer...")
                    answer_prompt = f"""Based on the following search results from uploaded documents, answer the user's question:

User question: {message}

Search results:
{document_search_result}

Provide a clear, comprehensive answer based on the search results. If the search results don't fully answer the question, say so."""
                    
                    answer_response = groq_client.chat.completions.create(
                        model="qwen/qwen3-32b",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that answers questions based on document content."},
                            {"role": "user", "content": answer_prompt}
                        ],
                        temperature=0.3,
                        max_tokens=1024
                    )
                    document_search_result = answer_response.choices[0].message.content
                    print(f"Document search answer generated ({len(document_search_result)} chars)")
            except Exception as e:
                document_search_error = f"Document search failed: {str(e)}"
                print(f"Document search error: {document_search_error}")
                import traceback
                traceback.print_exc()
        
        # Perform web search if needed
        web_research_result = None
        web_research_error = None
        if query_type in ['web_search_only', 'both']:
            print(f"Performing web research for query: {message[:100]}")
            research_session_id = f"{session_id}_research"
            web_research_result, web_research_error = perform_web_research(message, research_session_id)
            if web_research_error:
                print(f"Web research error: {web_research_error}")
                if query_type == 'web_search_only':
                    return jsonify({
                        'response': f'Web research failed: {web_research_error}. Please check that EXA_API_KEY is configured in your .env file.',
                        'error': web_research_error,
                        'has_research': False
                    }), 500
            else:
                print(f"Web research completed. Result length: {len(web_research_result) if web_research_result else 0}")
        
        # Perform CSV analysis if needed
        csv_analysis_result = None
        csv_charts = []
        csv_execution_output = []
        csv_code = None
        csv_error = None
        
        if query_type in ['csv_only', 'both']:
            print(f"Performing CSV analysis for query: {message[:100]}")
            if not has_csv:
                return jsonify({
                    'error': 'Please upload a data file (CSV or Excel .xlsx) first',
                    'session_id': session_id
                }), 400
            
            try:
                sbx = get_or_create_sandbox(session_id)
                
                # Use selected files (or all if only one)
                files_to_analyze = selected_files if selected_files else csv_files
                
                if len(files_to_analyze) == 0:
                    return jsonify({
                        'error': 'No CSV files selected for analysis',
                        'session_id': session_id
                    }), 400
                
                # If both data file and web search, incorporate web research context
                context_note = ""
                if query_type == 'both' and web_research_result:
                    context_note = f"\n\nIMPORTANT: The user also asked for web research. Here's what was found:\n{web_research_result}\n\nYou can use this context to enhance your analysis, but focus on analyzing the data file."
                
                # Build file information (simplified - single sheet per file)
                files_info_text = ""
                load_instructions = ""
                
                if len(files_to_analyze) == 1:
                    # Single file
                    file_info = files_to_analyze[0]
                    file_type = file_info.get('file_type', 'csv')
                    file_type_name = 'Excel' if file_type == 'excel' else 'CSV'
                    filename = file_info['filename']
                    columns_info = file_info.get('columns_info', {})
                    columns_list = columns_info.get('columns', [])
                    shape = columns_info.get('shape', [0, 0])
                    
                    files_info_text = f"""A {file_type_name} file has been uploaded:
- Filename: {filename}
- Path in sandbox: {file_info['sandbox_path']}
- Columns: {', '.join(columns_list)}
- Shape: {shape[0]} rows x {shape[1]} columns"""
                    
                    if file_type == 'excel':
                        load_instructions = f"df = pd.read_excel(\"{file_info['sandbox_path']}\", engine='openpyxl')"
                    else:
                        load_instructions = f'df = pd.read_csv("{file_info["sandbox_path"]}")'
                else:
                    # Multiple files
                    files_info_text = f"{len(files_to_analyze)} data files have been uploaded:\n"
                    load_instructions = "# Load multiple files:\n"
                    
                    for idx, file_info in enumerate(files_to_analyze):
                        filename = file_info['filename']
                        file_type = file_info.get('file_type', 'csv')
                        file_type_name = 'Excel' if file_type == 'excel' else 'CSV'
                        columns_list = file_info.get('columns_info', {}).get('columns', [])
                        shape = file_info.get('columns_info', {}).get('shape', [0, 0])
                        
                        files_info_text += f"\n{idx + 1}. {filename} ({file_type_name}):\n"
                        files_info_text += f"   - Path: {file_info['sandbox_path']}\n"
                        files_info_text += f"   - Columns: {', '.join(columns_list[:10])}{'...' if len(columns_list) > 10 else ''}\n"
                        files_info_text += f"   - Shape: {shape[0]} rows x {shape[1]} columns\n"
                        
                        if file_type == 'excel':
                            load_instructions += f"df{idx + 1} = pd.read_excel(\"{file_info['sandbox_path']}\", engine='openpyxl')\n"
                        else:
                            load_instructions += f"df{idx + 1} = pd.read_csv(\"{file_info['sandbox_path']}\")\n"
                
                # Build the system prompt
                if len(files_to_analyze) == 1:
                    system_prompt = f"""You are a Python code generator for data analysis. {files_info_text}{context_note}

CRITICAL: You MUST respond with ONLY executable Python code wrapped in ```python and ``` markers.
DO NOT include any explanations, text, or commentary outside the code block.

When the user asks for analysis, generate Python code to:
1. Load the data file using pandas:
   {load_instructions}
2. Perform the requested analysis"""
                else:
                    system_prompt = f"""You are a Python code generator for data analysis. {files_info_text}{context_note}

CRITICAL: You MUST respond with ONLY executable Python code wrapped in ```python and ``` markers.
DO NOT include any explanations, text, or commentary outside the code block.

IMPORTANT: You have access to {len(files_to_analyze)} data files. Based on the user's query, you may need to:
- Use one specific file that's most relevant
- Combine/merge multiple files if the query requires it
- Compare data across files

When the user asks for analysis, generate Python code to:
1. Load the relevant data file(s) using pandas:
{load_instructions}
   Use the file(s) that are most relevant to the user's query. If you need to combine files, use pd.merge() or pd.concat().
2. Perform the requested analysis"""
                
                # Common instructions for both single and multiple files
                common_instructions = """
3. CRITICAL: Always include print() statements to output results:
   - For column names: print(list(df.columns)) or print(', '.join(df.columns))
   - For statistics: print(df.describe().to_string())
   - For dataframes: print(df.head().to_string()) or print(df.to_string())
   - For single values: print(str(value))
   - NEVER just print(df.columns) - convert Index to list first: print(list(df.columns))
   - NEVER just print(df) - use .to_string(): print(df.to_string())
4. Create visualizations using matplotlib when appropriate
5. CRITICAL: To generate charts that will be displayed:
   - Always call plt.show() at the end of your plotting code - this is REQUIRED for the chart to be captured
   - You can optionally also save with: plt.savefig('/home/user/chart.png', bbox_inches='tight', dpi=150)
   - But plt.show() MUST be called for the chart to appear in the results
6. Example plotting code structure:
   ```python
   import pandas as pd
   import matplotlib.pyplot as plt
   
   # Load data
   df = pd.read_csv("/path/to/file.csv")
   
   # Prepare data for plotting
   # ... your data manipulation here ...
   
   # Create plot
   plt.figure(figsize=(10, 6))
   plt.plot(x_data, y_data)
   plt.xlabel('X Label')
   plt.ylabel('Y Label')
   plt.title('Chart Title')
   plt.grid(True, alpha=0.3)
   plt.show()  # THIS IS REQUIRED - do not skip this!
   ```

CODE FORMAT REQUIREMENTS:
- Use proper Python indentation (4 spaces per level)
- All code blocks after if/else/for/while/def must be indented
- Ensure all code is syntactically correct and executable
- Use consistent indentation throughout
- Import all necessary libraries (pandas, matplotlib.pyplot, numpy, etc.)

RESPONSE FORMAT - ABSOLUTELY CRITICAL:
Your response MUST be ONLY Python code in this exact format:
```python
import pandas as pd
import matplotlib.pyplot as plt

# Your code here
df = pd.read_csv("...")
# ... analysis code ...
print(results)
plt.show()  # if creating plots
```

DO NOT include:
- Explanations before the code block
- Text after the code block
- Comments about what you're going to do
- Summaries of the code

Just the code block, nothing else."""

                system_prompt += common_instructions

                # STEP 1: ALWAYS EXECUTE df.head() FIRST to ground the analysis
                print("=" * 80)
                print("STEP 1: Loading data preview (df.head()) for schema grounding...")
                print("=" * 80)
                
                data_preview_code = ""
                
                for idx, file_info in enumerate(files_to_analyze):
                    file_path = file_info['sandbox_path']
                    file_type = file_info.get('file_type', 'csv')
                    filename = file_info['filename']
                    
                    if file_type == 'excel':
                        data_preview_code += f"""
# Preview for {filename}
df_preview_{idx} = pd.read_excel("{file_path}", engine='openpyxl')
print("\\n{'=' * 60}")
print("DATA PREVIEW: {filename}")
print("{'=' * 60}")
print("Columns:", list(df_preview_{idx}.columns))
print("Shape:", df_preview_{idx}.shape)
print("Data types:")
print(df_preview_{idx}.dtypes)
print("\\nFirst 10 rows:")
print(df_preview_{idx}.head(10).to_string())
print("\\nSummary statistics:")
print(df_preview_{idx}.describe())
"""
                    else:
                        data_preview_code += f"""
# Preview for {filename}
df_preview_{idx} = pd.read_csv("{file_path}")
print("\\n{'=' * 60}")
print("DATA PREVIEW: {filename}")
print("{'=' * 60}")
print("Columns:", list(df_preview_{idx}.columns))
print("Shape:", df_preview_{idx}.shape)
print("Data types:")
print(df_preview_{idx}.dtypes)
print("\\nFirst 10 rows:")
print(df_preview_{idx}.head(10).to_string())
print("\\nSummary statistics:")
print(df_preview_{idx}.describe())
"""
                
                # Execute preview code to get actual data context
                preview_code = f"""
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
{data_preview_code}
"""
                
                preview_output = ""
                try:
                    print("Executing data preview code...")
                    preview_result = sbx.run_code(preview_code)
                    
                    if preview_result.error:
                        print(f"ERROR in preview execution: {preview_result.error}")
                        csv_execution_output.append(f"⚠️ Data preview failed: {preview_result.error}")
                    else:
                        if preview_result.logs and preview_result.logs.stdout:
                            preview_output = ''.join(preview_result.logs.stdout)
                            print(f"✓ Data preview captured successfully ({len(preview_output)} chars)")
                            # Add preview output to execution output so user sees it
                            csv_execution_output.append("=" * 60)
                            csv_execution_output.append("DATA PREVIEW (Schema & Sample)")
                            csv_execution_output.append("=" * 60)
                            csv_execution_output.append(preview_output[:2000])  # Limit to avoid too much output
                            if len(preview_output) > 2000:
                                csv_execution_output.append("... (preview truncated)")
                        else:
                            print("WARNING: Preview executed but no output captured")
                    
                    # Add data preview to system prompt for LLM grounding
                    if preview_output:
                        system_prompt += f"\n\n{'=' * 60}\nCRITICAL: ACTUAL DATA SCHEMA & PREVIEW\n{'=' * 60}\n{preview_output[:3000]}\n\nYou MUST use these EXACT column names and data types from the preview above when generating analysis code. Do not make assumptions about column names or data structure."
                    
                except Exception as e:
                    error_msg = f"Failed to load data preview: {str(e)}"
                    print(f"ERROR: {error_msg}")
                    csv_execution_output.append(f"⚠️ {error_msg}")
                    import traceback
                    traceback.print_exc()

                # STEP 2: Generate and execute code with automatic retry loop
                print("=" * 80)
                print("STEP 2: Code generation and execution with auto-retry...")
                print("=" * 80)
                
                MAX_RETRIES = 10
                retry_count = 0
                execution_successful = False
                conversation_history = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
                
                while retry_count < MAX_RETRIES and not execution_successful:
                    attempt_num = retry_count + 1
                    print(f"\n{'='*60}")
                    print(f"ATTEMPT {attempt_num}/{MAX_RETRIES}")
                    print(f"{'='*60}")
                    
                    # Generate code
                    print(f"Calling Groq to generate code (attempt {attempt_num})...")
                    groq_response = groq_client.chat.completions.create(
                        model="qwen/qwen3-32b",
                        messages=conversation_history,
                        temperature=0.1 if retry_count == 0 else 0.05,
                        max_tokens=2048
                    )
                    response_text = groq_response.choices[0].message.content
                    csv_code = extract_code_from_response(response_text)
                    
                    if not csv_code:
                        print(f"❌ Attempt {attempt_num}: Failed to extract code from response")
                        # Add error feedback to conversation
                        conversation_history.append({"role": "assistant", "content": response_text})
                        conversation_history.append({
                            "role": "user",
                            "content": f"ERROR: No valid Python code was found in your response. Please provide ONLY a Python code block wrapped in ```python and ```. No explanations, just the code."
                        })
                        retry_count += 1
                        continue
                    
                    print(f"✓ Extracted code: {len(csv_code)} chars")
                    
                    # Validate syntax
                    print(f"Validating syntax...")
                    syntax_error = None
                    try:
                        compile(csv_code, '<string>', 'exec')
                        print("✓ Syntax is valid")
                    except SyntaxError as e:
                        syntax_error = f"Syntax error: {e.msg} on line {e.lineno}"
                        print(f"❌ {syntax_error}")
                        
                        # Add error feedback to conversation for retry
                        conversation_history.append({"role": "assistant", "content": f"```python\n{csv_code}\n```"})
                        conversation_history.append({
                            "role": "user",
                            "content": f"""ERROR: The code has a syntax error:
{syntax_error}

Please fix this error and provide corrected Python code. Remember:
- Use proper string delimiters (quotes)
- Check for unterminated strings
- Ensure proper indentation
- Close all brackets and parentheses

Provide ONLY the corrected code in a ```python code block."""
                        })
                        retry_count += 1
                        continue
                    
                    # Execute code
                    print(f"Executing code in sandbox...")
                    execution = sbx.run_code(csv_code)
                    
                    # Check for execution errors
                    if execution.error:
                        execution_error = f"{execution.error.name}: {execution.error.value}"
                        print(f"❌ Execution error: {execution_error}")
                        
                        # Capture any output before error
                        output_before_error = ""
                        if hasattr(execution, 'logs'):
                            if hasattr(execution.logs, 'stdout') and execution.logs.stdout:
                                output_before_error = ''.join(execution.logs.stdout).strip()
                            if hasattr(execution.logs, 'stderr') and execution.logs.stderr:
                                stderr = ''.join(execution.logs.stderr).strip()
                                if stderr:
                                    output_before_error += f"\nSTDERR: {stderr}"
                        
                        # Add error feedback to conversation for retry
                        error_context = f"""ERROR: The code executed but failed with this error:
{execution_error}"""
                        
                        if output_before_error:
                            error_context += f"\n\nOutput before error:\n{output_before_error[:500]}"
                        
                        error_context += f"""

Please analyze the error and fix the code. Common issues:
- Column name errors: Check the data preview for exact column names
- Data type errors: Convert types appropriately (int(), float(), str())
- Index errors: Check data shape and bounds
- Key errors: Ensure dictionary keys exist
- Attribute errors: Check object has the attribute

Provide ONLY the corrected Python code in a ```python code block."""
                        
                        conversation_history.append({"role": "assistant", "content": f"```python\n{csv_code}\n```"})
                        conversation_history.append({"role": "user", "content": error_context})
                        retry_count += 1
                        continue
                    
                    # Success!
                    print(f"✓ Code executed successfully on attempt {attempt_num}")
                    execution_successful = True
                
                # Handle final result
                if not execution_successful:
                    csv_error = f"Code failed to execute successfully after {MAX_RETRIES} attempts"
                    print(f"❌ {csv_error}")
                    csv_execution_output.append("")
                    csv_execution_output.append("=" * 60)
                    csv_execution_output.append(f"FAILED AFTER {MAX_RETRIES} ATTEMPTS")
                    csv_execution_output.append("=" * 60)
                    csv_execution_output.append(csv_error)
                    
                    if query_type == 'csv_only':
                        return jsonify({
                            'error': csv_error,
                            'code': csv_code,
                            'execution_output': csv_execution_output,
                            'has_code': csv_code is not None,
                            'error': True
                        }), 500
                
                # If successful, continue with result processing
                if execution_successful:
                    print("=" * 80)
                    print("STEP 3: Processing successful execution results...")
                    print("=" * 80)
                    
                    # Capture execution results
                    execution_has_output = False
                    
                    csv_execution_output.append("")
                    csv_execution_output.append("=" * 60)
                    csv_execution_output.append("EXECUTION RESULTS")
                    csv_execution_output.append("=" * 60)
                    
                    if hasattr(execution, 'logs'):
                        if hasattr(execution.logs, 'stdout') and execution.logs.stdout:
                            stdout_text = ''.join(execution.logs.stdout).strip()
                            if stdout_text:
                                csv_execution_output.append(stdout_text)
                                execution_has_output = True
                                print(f"✓ Captured stdout: {len(stdout_text)} chars")
                            else:
                                print("⚠️ stdout is empty")
                        else:
                            print("⚠️ No stdout attribute")
                        
                        if hasattr(execution.logs, 'stderr') and execution.logs.stderr:
                            stderr_text = ''.join(execution.logs.stderr).strip()
                            if stderr_text:
                                csv_execution_output.append("")
                                csv_execution_output.append("STDERR:")
                                csv_execution_output.append(stderr_text)
                                execution_has_output = True
                                print(f"✓ Captured stderr: {len(stderr_text)} chars")
                        
                        # Always add execution status if no output was captured
                        if not execution_has_output:
                            csv_execution_output.append("✓ Code executed successfully")
                            csv_execution_output.append("(No output produced - the code may be missing print() statements)")
                            print("⚠️ Code executed but produced no output")
                    else:
                        print("⚠️ Execution has no logs attribute")
                        csv_execution_output.append("✓ Code executed")
                        csv_execution_output.append("(Unable to capture output)")
                    
                    # Process results for charts
                    # First, check for PNG results from plt.show()
                    print(f"Checking execution.results for charts (found {len(execution.results) if execution.results else 0} results)")
                    for idx, result in enumerate(execution.results):
                        print(f"Result {idx}: type={type(result)}, hasattr(png)={hasattr(result, 'png')}")
                        if hasattr(result, 'png') and result.png:
                            print(f"Found PNG result {idx}, size: {len(result.png) if result.png else 0} bytes")
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            chart_filename = f"chart_{session_id}_{timestamp}.png"
                            chart_path = CHARTS_DIR / chart_filename
                            
                            with open(chart_path, 'wb') as f:
                                f.write(base64.b64decode(result.png))
                            
                            csv_charts.append({
                                'filename': chart_filename,
                                'url': f'/api/chart/{chart_filename}'
                            })
                            print(f"Saved chart from plt.show(): {chart_filename}")
                        else:
                            print(f"Result {idx} does not have PNG data")
                    
                    # Also check for saved chart files in sandbox (from plt.savefig)
                    chart_paths_to_check = [
                        '/home/user/chart.png',
                        '/home/user/charts/chart.png',
                        '/home/user/plot.png',
                    ]
                    
                    chart_found = False
                    for sandbox_chart_path in chart_paths_to_check:
                        try:
                            # Try to read file directly using sandbox files API
                            try:
                                if hasattr(sbx, 'files') and hasattr(sbx.files, 'read'):
                                    chart_data = sbx.files.read(sandbox_chart_path)
                                    if chart_data:
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        chart_filename = f"chart_{session_id}_{timestamp}.png"
                                        chart_path = CHARTS_DIR / chart_filename
                                        
                                        with open(chart_path, 'wb') as f:
                                            f.write(chart_data)
                                        
                                        csv_charts.append({
                                            'filename': chart_filename,
                                            'url': f'/api/chart/{chart_filename}'
                                        })
                                        print(f"Saved chart from sandbox file (files API): {chart_filename}")
                                        chart_found = True
                                        break
                            except Exception as api_error:
                                print(f"Files API failed for {sandbox_chart_path}: {api_error}")
                        except Exception as e:
                            print(f"Error checking for chart at {sandbox_chart_path}: {e}")
                            continue
                    
                    if not chart_found and not csv_charts:
                        print("No charts found in execution.results or sandbox filesystem")
                    
                    # Generate explanation from execution results
                    results_summary = '\n'.join(csv_execution_output) if csv_execution_output else 'Code executed successfully.'
                    print(f"Generating explanation for CSV analysis...")
                    
                    if execution_has_output:
                        # Generate explanation from actual results
                        try:
                            explanation_prompt = f"""Based on this data analysis code and results, provide a clear, direct answer to the user's question:

User question: {message}

Code executed:
{csv_code}

Execution results:
{results_summary[:2000]}

Provide a clear, direct answer to the user's question based on the results. If the results contain the answer, state it clearly. If not, explain what was found."""

                            explanation_response = groq_client.chat.completions.create(
                                model="qwen/qwen3-32b",
                                messages=[
                                    {"role": "system", "content": "You are a data analysis expert. Answer questions directly based on the analysis results."},
                                    {"role": "user", "content": explanation_prompt}
                                ],
                                temperature=0.3,
                                max_tokens=1024
                            )
                            csv_analysis_result = explanation_response.choices[0].message.content
                            print(f"CSV analysis completed successfully")
                        except Exception as e:
                            print(f"Error generating explanation: {e}")
                            csv_analysis_result = f"Analysis completed. Results:\n{results_summary[:1000]}"
                    else:
                        csv_analysis_result = f"Code executed successfully after {retry_count + 1} attempt(s)."
                
            except Exception as e:
                csv_error = f"CSV analysis failed: {str(e)}"
                print(f"CSV analysis error: {csv_error}")
                import traceback
                traceback.print_exc()
                if query_type == 'csv_only':
                    return jsonify({
                        'error': csv_error,
                        'has_code': False
                    }), 500
        
        # Combine results based on query type
        if query_type == 'document_search':
            if not document_search_result:
                return jsonify({
                    'response': f'Document search completed but no results were returned. {document_search_error or "Please try rephrasing your query."}',
                    'has_documents': False,
                    'error': document_search_error
                })
            return jsonify({
                'response': document_search_result,
                'has_documents': True,
                'has_code': False
            })
        
        if query_type == 'web_search_only':
            if not web_research_result:
                return jsonify({
                    'response': 'Web search completed but no results were returned. Please try rephrasing your query or check the logs for errors.',
                    'has_research': False,
                    'has_code': False
                })
            return jsonify({
                'response': web_research_result,
                'has_research': True,
                'has_code': False
            })
        
        elif query_type == 'csv_only':
            print("=" * 80)
            print("FINAL RESPONSE FOR CSV_ONLY")
            print("=" * 80)
            print(f"  - Response length: {len(csv_analysis_result) if csv_analysis_result else 0}")
            print(f"  - Has code: {csv_code is not None}")
            print(f"  - Code length: {len(csv_code) if csv_code else 0}")
            print(f"  - Execution output items: {len(csv_execution_output)}")
            print(f"  - Charts: {len(csv_charts)}")
            if csv_execution_output:
                print("  - Execution output preview:")
                for i, item in enumerate(csv_execution_output[:3]):
                    print(f"    [{i}]: {item[:100]}")
            print("=" * 80)
            
            return jsonify({
                'response': csv_analysis_result or "Analysis completed.",
                'code': csv_code,
                'execution_output': csv_execution_output,
                'charts': csv_charts,
                'has_code': csv_code is not None,
                'error': False
            })
        
        elif query_type == 'both':
            # Combine web research and CSV analysis
            combined_response = ""
            errors = []
            
            if web_research_result:
                combined_response += f"## Web Research Results:\n\n{web_research_result}\n\n"
            elif web_research_error:
                errors.append(f"Web research failed: {web_research_error}")
            
            if csv_analysis_result:
                combined_response += f"## CSV Data Analysis:\n\n{csv_analysis_result}"
            elif csv_error:
                errors.append(f"CSV analysis failed: {csv_error}")
            
            if not combined_response:
                if errors:
                    combined_response = "## Error Summary\n\n" + "\n".join(errors)
                else:
                    combined_response = "Both web search and CSV analysis were attempted, but no results were returned. Please check the logs for details."
            
            return jsonify({
                'response': combined_response,
                'code': csv_code,
                'execution_output': csv_execution_output,
                'charts': csv_charts,
                'web_research': web_research_result,
                'has_code': csv_code is not None,
                'has_research': web_research_result is not None,
                'error': len(errors) > 0,
                'errors': errors if errors else None
            })
        
        return jsonify({
            'error': 'Unable to determine query type',
            'session_id': session_id
        }), 400
    
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart/<filename>')
def get_chart(filename):
    """Serve chart images"""
    try:
        chart_path = CHARTS_DIR / filename
        if chart_path.exists():
            return send_file(chart_path, mimetype='image/png')
        return jsonify({'error': 'Chart not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/close', methods=['POST'])
def close_session():
    """Close sandbox session"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        cleanup_sandbox(session_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup/all', methods=['POST'])
def cleanup_all():
    """Cleanup all sandboxes (admin endpoint)"""
    try:
        cleanup_all_sandboxes()
        return jsonify({'success': True, 'message': 'All sandboxes closed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fix_code_indentation(code):
    """Fix common indentation issues in Python code using a simple state machine"""
    lines = code.split('\n')
    fixed_lines = []
    indent_level = 0  # Current indent level (in spaces)
    indent_size = 4
    pending_indent = False  # Whether next line should be indented
    
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        
        # Skip empty lines and comments (preserve original)
        if not stripped or stripped.startswith('#'):
            fixed_lines.append(line)
            continue
        
        # Check if this is a dedent keyword
        is_dedent = stripped.startswith(('elif ', 'else:', 'except ', 'finally:'))
        
        # If previous line ended with ':', next line should be indented (unless it's a dedent keyword)
        if pending_indent and not is_dedent:
            indent_level += indent_size
            pending_indent = False
        
        # Handle dedent keywords - they should be at the same level as the matching if/try
        if is_dedent:
            # Dedent by one level
            indent_level = max(0, indent_level - indent_size)
        
        # Apply indentation
        fixed_line = ' ' * indent_level + stripped
        fixed_lines.append(fixed_line)
        
        # Check if this line ends with ':' and starts a block
        if stripped.endswith(':') and not stripped.startswith('#'):
            pending_indent = True
        else:
            pending_indent = False
    
    return '\n'.join(fixed_lines)

def extract_code_from_response(text):
    """Extract Python code from markdown code blocks and fix indentation"""
    import re
    
    print(f"Attempting to extract code from response (length: {len(text)} chars)")
    print(f"Response preview: {text[:200]}...")
    
    # Try to find code block with python marker
    pattern = r'```python\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        print(f"✓ Found Python code block (method 1): {len(code)} chars")
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
    # Try to find any code block
    pattern = r'```\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        print(f"✓ Found generic code block (method 2): {len(code)} chars")
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
    # Try without newline after opening backticks
    pattern = r'```python(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        print(f"✓ Found Python code block without newline (method 3): {len(code)} chars")
        code = fix_code_indentation(code)
        return code
    
    # Try generic without newline
    pattern = r'```(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        print(f"✓ Found generic code block without newline (method 4): {len(code)} chars")
        code = fix_code_indentation(code)
        return code
    
    # If no code blocks, check if entire response looks like code
    if 'import' in text and ('pandas' in text or 'matplotlib' in text or 'pd.' in text or 'plt.' in text):
        print(f"✓ Response appears to be raw Python code (method 5)")
        code = text.strip()
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
    # Last resort: if it has df. or pd. operations, assume it's code
    if ('df.' in text or 'pd.' in text) and len(text.split('\n')) > 2:
        print(f"⚠️ Response contains pandas operations, treating as code (method 6)")
        code = text.strip()
        code = fix_code_indentation(code)
        return code
    
    print(f"❌ Could not extract code from response. Response content:")
    print(text[:500])
    return None

@app.route('/api/research', methods=['POST'])
def research():
    """Handle deep research queries using E2B MCP sandbox with Exa for web search"""
    try:
        data = request.json
        query = data.get('query', '')
        session_id = data.get('session_id', 'default_research')
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        
        # Check if Exa API key is configured
        exa_api_key = os.getenv('EXA_API_KEY')
        if not exa_api_key:
            return jsonify({
                'error': 'EXA_API_KEY not configured. Please add it to your .env file.'
            }), 500
        
        print(f"Starting research query: {query}")
        
        # Get or create research sandbox with MCP (Exa)
        if session_id not in research_sandboxes:
            print(f"Creating new MCP-enabled sandbox for session: {session_id}")
            try:
                # Create E2B sandbox with Exa MCP server
                research_sandbox = E2BSandbox.create(
                    mcp={
                        "exa": {
                            "apiKey": exa_api_key
                        }
                    }
                )
                research_sandboxes[session_id] = research_sandbox
                print(f"MCP sandbox created. MCP URL: {research_sandbox.get_mcp_url()}")
            except Exception as e:
                print(f"Error creating MCP sandbox: {e}")
                return jsonify({
                    'error': f'Failed to create research sandbox: {str(e)}'
                }), 500
        else:
            research_sandbox = research_sandboxes[session_id]
        
        # Get MCP URL and token (try different method names for Python SDK)
        try:
            # Try Python SDK method names (snake_case)
            if hasattr(research_sandbox, 'get_mcp_url'):
                mcp_url = research_sandbox.get_mcp_url()
            elif hasattr(research_sandbox, 'getMcpUrl'):
                mcp_url = research_sandbox.getMcpUrl()
            else:
                # Fallback: try accessing as attribute
                mcp_url = getattr(research_sandbox, 'mcp_url', None)
            
            if hasattr(research_sandbox, 'get_mcp_token'):
                mcp_token = research_sandbox.get_mcp_token()
            elif hasattr(research_sandbox, 'getMcpToken'):
                mcp_token = research_sandbox.getMcpToken()
            else:
                # Fallback: try accessing as attribute
                mcp_token = getattr(research_sandbox, 'mcp_token', None)
            
            if not mcp_url or not mcp_token:
                raise ValueError("Could not retrieve MCP URL or token from sandbox")
            
            print(f"Using MCP URL: {mcp_url}")
        except Exception as e:
            print(f"Error getting MCP URL/token: {e}")
            return jsonify({
                'error': f'Failed to get MCP configuration: {str(e)}. The E2B Python SDK may have different method names for MCP access.'
            }), 500
        
        # Create research prompt
        research_prompt = f"""{query}

Use Exa to search for recent and relevant information to answer this question comprehensively. 
Provide a detailed summary with sources and key findings."""
        
        # Call Groq with MCP tools
        try:
            print("Calling Groq with MCP tools...")
            # Try using chat.completions with MCP tools
            # Note: Groq may need to support MCP tools format
            response = groq_client.chat.completions.create(
                model="qwen/qwen3-32b",  # Using the same model as CSV analysis
                messages=[
                    {
                        "role": "system",
                        "content": "You are a research assistant. Use the available tools to search the web and provide comprehensive, well-sourced answers."
                    },
                    {
                        "role": "user",
                        "content": research_prompt
                    }
                ],
                tools=[
                    {
                        "type": "mcp",
                        "server_label": "e2b-mcp-gateway",
                        "server_url": mcp_url,
                        "headers": {
                            "Authorization": f"Bearer {mcp_token}"
                        }
                    }
                ],
                temperature=0.7,
                max_tokens=2048
            )
            
            # Extract response
            research_result = response.choices[0].message.content
            
            print(f"Research completed. Response length: {len(research_result)}")
            
            return jsonify({
                'success': True,
                'query': query,
                'response': research_result,
                'session_id': session_id,
                'has_research': True
            })
            
        except Exception as e:
            print(f"Error during research: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'Research failed: {str(e)}',
                'has_research': False
            }), 500
    
    except Exception as e:
        print(f"Error in research endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/research/close', methods=['POST'])
def close_research_session():
    """Close research sandbox session"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default_research')
        
        if session_id in research_sandboxes:
            try:
                research_sandbox = research_sandboxes[session_id]
                research_sandbox.kill()
                print(f"Closed research sandbox for session: {session_id}")
            except Exception as e:
                print(f"Error closing research sandbox {session_id}: {e}")
            del research_sandboxes[session_id]
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

