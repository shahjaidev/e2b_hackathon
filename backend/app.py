import os
import base64
import json
import atexit
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
from e2b import Sandbox as E2BSandbox
from groq import Groq
from openai import OpenAI

# Import company data validator
from validators.company_schema import (
    validate_company_data,
    is_company_data,
    get_company_summary,
    normalize_csv_to_company_data
)

# Import competitor analysis components
from services.competitor_discovery import discover_competitors
from scrapers.browserbase_mcp import (
    create_browserbase_sandbox,
    scrape_competitor_pages
)
from extractors.groq_extractor import extract_all_competitor_data
from generators.comparison_table import generate_comparison_table

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
# Store browserbase sandboxes (MCP-enabled for scraping)
browserbase_sandboxes = {}

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
    
    # Also cleanup browserbase sandboxes
    print("Cleaning up browserbase sandboxes...")
    for session_id, sandbox in list(browserbase_sandboxes.items()):
        try:
            if hasattr(sandbox, 'kill'):
                sandbox.kill()
            elif hasattr(sandbox, 'close'):
                sandbox.close()
            print(f"Closed browserbase sandbox for session: {session_id}")
        except Exception as e:
            print(f"Error closing browserbase sandbox {session_id}: {e}")
    browserbase_sandboxes.clear()

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

def get_or_create_browserbase_sandbox(session_id):
    """
    Get existing Browserbase MCP sandbox or create new one with both Exa and Browserbase
    
    Args:
        session_id: Session identifier
        
    Returns:
        E2B MCP sandbox with Browserbase and Exa enabled
    """
    browserbase_session_id = f"{session_id}_browserbase"
    
    if browserbase_session_id in browserbase_sandboxes:
        print(f"♻️  Reusing existing Browserbase sandbox for session: {session_id}")
        return browserbase_sandboxes[browserbase_session_id]
    
    print(f"🌐 Creating new Browserbase MCP sandbox for session: {session_id}")
    
    # Get API keys
    browserbase_api_key = os.getenv('BROWSERBASE_API_KEY')
    browserbase_project_id = os.getenv('BROWSERBASE_PROJECT_ID')
    exa_api_key = os.getenv('EXA_API_KEY')
    
    if not browserbase_api_key or not browserbase_project_id:
        raise ValueError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in environment variables")
    
    # Create MCP config with both Browserbase and Exa
    mcp_config = {
        "browserbase": {
            "apiKey": browserbase_api_key,
            "projectId": browserbase_project_id
        }
    }
    
    # Add Exa if available (for combined operations)
    if exa_api_key:
        mcp_config["exa"] = {"apiKey": exa_api_key}
        print("   Including Exa MCP for combined operations")
    
    try:
        sandbox = E2BSandbox.create(mcp=mcp_config)
        browserbase_sandboxes[browserbase_session_id] = sandbox
        print(f"✅ Browserbase MCP sandbox created successfully")
        return sandbox
    except Exception as e:
        print(f"❌ Failed to create Browserbase sandbox: {e}")
        raise

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
    elif filename_lower.endswith(('.xls', '.xlsx', '.xlsm')):
        return 'excel'
    elif filename_lower.endswith('.json'):
        return 'json'
    elif filename_lower.endswith('.pdf'):
        return 'pdf'
    return None

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
            return jsonify({'error': 'Only CSV, JSON, Excel (.xlsx, .xlsm), and PDF files are allowed'}), 400
        
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
        if file_type == 'pdf':
            # Handle PDF files - extract text
            analysis_code = f"""
import json
try:
    import PyPDF2
    
    with open("{sandbox_path.path}", 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        num_pages = len(pdf_reader.pages)
        
        # Extract text from all pages
        text_content = []
        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text_content.append(page.extract_text())
        
        full_text = '\\n'.join(text_content)
        
        columns_info = {{
            'columns': ['page_number', 'text_content'],
            'shape': [num_pages, 2],
            'dtypes': {{'page_number': 'int', 'text_content': 'str'}},
            'sample': [
                {{'page_number': i+1, 'text_content': text_content[i][:200] + '...'}}
                for i in range(min(3, num_pages))
            ],
            'file_type': 'pdf',
            'num_pages': num_pages,
            'total_text_length': len(full_text)
        }}
        
        print(json.dumps(columns_info))
except ImportError:
    # PyPDF2 not installed, try installing it
    import subprocess
    subprocess.check_call(['pip', 'install', 'PyPDF2'])
    
    # Retry after installation
    import PyPDF2
    with open("{sandbox_path.path}", 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        num_pages = len(pdf_reader.pages)
        text_content = []
        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text_content.append(page.extract_text())
        full_text = '\\n'.join(text_content)
        columns_info = {{
            'columns': ['page_number', 'text_content'],
            'shape': [num_pages, 2],
            'dtypes': {{'page_number': 'int', 'text_content': 'str'}},
            'sample': [
                {{'page_number': i+1, 'text_content': text_content[i][:200] + '...'}}
                for i in range(min(3, num_pages))
            ],
            'file_type': 'pdf',
            'num_pages': num_pages,
            'total_text_length': len(full_text)
        }}
        print(json.dumps(columns_info))
except Exception as e:
    columns_info = {{
        'columns': [],
        'shape': [0, 0],
        'dtypes': {{}},
        'sample': [],
        'error': str(e),
        'file_type': 'pdf'
    }}
    print(json.dumps(columns_info))
"""
        elif file_type == 'json':
            # Handle JSON files (common for company data)
            analysis_code = f"""
import json

try:
    with open("{sandbox_path.path}", 'r') as f:
        data = json.load(f)
    
    # JSON can be a single object or array
    if isinstance(data, dict):
        columns_info = {{
            'columns': list(data.keys()),
            'shape': [1, len(data.keys())],
            'dtypes': {{k: type(v).__name__ for k, v in data.items()}},
            'sample': [data]
        }}
    elif isinstance(data, list) and len(data) > 0:
        first_item = data[0]
        columns_info = {{
            'columns': list(first_item.keys()) if isinstance(first_item, dict) else [],
            'shape': [len(data), len(first_item.keys()) if isinstance(first_item, dict) else 0],
            'dtypes': {{k: type(v).__name__ for k, v in first_item.items()}} if isinstance(first_item, dict) else {{}},
            'sample': data[:3]
        }}
    else:
        columns_info = {{
            'columns': [],
            'shape': [0, 0],
            'dtypes': {{}},
            'sample': []
        }}
    
    print(json.dumps(columns_info))
except Exception as e:
    columns_info = {{
        'columns': [],
        'shape': [0, 0],
        'dtypes': {{}},
        'sample': [],
        'error': str(e)
    }}
    print(json.dumps(columns_info))
"""
        elif file_type == 'csv':
            analysis_code = f"""
import pandas as pd
import json
# Read only first few rows to get structure quickly
df = pd.read_csv("{sandbox_path.path}", nrows=100)
# Get row count efficiently
try:
    with open("{sandbox_path.path}", 'r') as f:
        total_rows = sum(1 for line in f) - 1  # Subtract header
except:
    total_rows = len(df)
columns_info = {{
    'columns': list(df.columns),
    'shape': [total_rows, len(df.columns)],
    'dtypes': df.dtypes.astype(str).to_dict(),
    'sample': df.head(3).to_dict(orient='records')
}}
print(json.dumps(columns_info))
"""
        else:  # excel
            analysis_code = f"""
import pandas as pd
import json

try:
    # Get all sheet names
    xl_file = pd.ExcelFile("{sandbox_path.path}")
    sheet_names = xl_file.sheet_names
except Exception as e:
    # If Excel reading fails, return error info
    columns_info = {{
        'columns': [],
        'shape': [0, 0],
        'dtypes': {{}},
        'sample': [],
        'error': f'Failed to read Excel file: {{str(e)}}',
        'sheets': {{}},
        'sheet_names': [],
        'default_sheet': None
    }}
    print(json.dumps(columns_info))
    exit(0)

# Analyze each sheet
sheets_info = {{}}

# Analyze each sheet
sheets_info = {{}}
for sheet_name in sheet_names:
    try:
        # Read only first few rows to get structure quickly
        df = pd.read_excel("{sandbox_path.path}", sheet_name=sheet_name, nrows=100)
        # Get row count efficiently
        try:
            # For Excel files, read the full sheet to get accurate row count
            df_full = pd.read_excel("{sandbox_path.path}", sheet_name=sheet_name)
            total_rows = len(df_full)
        except:
            total_rows = len(df)
        
        sheets_info[sheet_name] = {{
            'columns': list(df.columns),
            'shape': [total_rows, len(df.columns)],
            'dtypes': df.dtypes.astype(str).to_dict(),
            'sample': df.head(3).to_dict(orient='records')
        }}
    except Exception as e:
        sheets_info[sheet_name] = {{
            'columns': [],
            'shape': [0, 0],
            'dtypes': {{}},
            'sample': [],
            'error': str(e)
        }}

# If only one sheet, also include it at the top level for backward compatibility
if len(sheet_names) == 1:
    default_sheet = sheet_names[0]
    columns_info = {{
        'columns': sheets_info[default_sheet]['columns'],
        'shape': sheets_info[default_sheet]['shape'],
        'dtypes': sheets_info[default_sheet]['dtypes'],
        'sample': sheets_info[default_sheet]['sample'],
        'sheets': sheets_info,
        'sheet_names': sheet_names,
        'default_sheet': default_sheet
    }}
else:
    # For multiple sheets, use the first sheet as default but include all sheets info
    default_sheet = sheet_names[0]
    columns_info = {{
        'columns': sheets_info[default_sheet]['columns'],
        'shape': sheets_info[default_sheet]['shape'],
        'dtypes': sheets_info[default_sheet]['dtypes'],
        'sample': sheets_info[default_sheet]['sample'],
        'sheets': sheets_info,
        'sheet_names': sheet_names,
        'default_sheet': default_sheet
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
                'shape': (0, 0),
                'dtypes': {},
                'sample': []
            }
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
        
            uploaded_files[session_id] = {
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'local_path': str(filepath),
                'file_type': file_type,
                'columns_info': columns_info
            }
            
            # NEW: Check if this is company data and validate
            print("Checking if uploaded file is company data...")
            
            # Try to detect company data from columns or sample data
            sample_data = columns_info.get('sample', [])
            if sample_data and len(sample_data) > 0:
                # Convert first row to dict for validation
                first_row = sample_data[0]
                
                # Check if it looks like company data
                if is_company_data(first_row):
                    print("Detected company data! Validating schema...")
                    
                    # Normalize CSV data to company format
                    normalized_data = normalize_csv_to_company_data(first_row)
                    
                    # Validate company data
                    is_valid, company_data, errors = validate_company_data(normalized_data)
                    
                    if is_valid:
                        print(f"✅ Valid company data: {company_data.get('company_name')}")
                        
                        # Store company data in session
                        uploaded_files[session_id]['is_company_data'] = True
                        uploaded_files[session_id]['company_data'] = company_data
                        
                        # Get summary for response
                        company_summary = get_company_summary(company_data)
                        
                        print(f"Upload completed successfully. Company: {company_summary['company_name']}")
                        return jsonify({
                            'success': True,
                            'filename': file.filename,
                            'sandbox_path': sandbox_path.path,
                            'columns_info': columns_info,
                            'session_id': session_id,
                            'is_company_data': True,
                            'company_summary': company_summary
                        })
                    else:
                        print(f"⚠️  Company data validation failed: {errors}")
                        # Return error with details
                        return jsonify({
                            'error': 'Invalid company data',
                            'details': errors,
                            'filename': file.filename
                        }), 400
            
            # Not company data - return normal CSV response
            print(f"Upload completed successfully. Columns: {len(columns_info.get('columns', []))}")
            return jsonify({
                'success': True,
                'filename': file.filename,
                'sandbox_path': sandbox_path.path,
                'columns_info': columns_info,
                'session_id': session_id,
                'is_company_data': False
            })
    
    except Exception as e:
        print(f"Error in upload_file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def determine_query_type_with_llm(message, has_csv_data=False, csv_columns=None):
    """Use LLM to determine if query needs CSV analysis, web search, or both"""
    try:
        # Simple, clear prompt for Groq to detect intent
        prompt = f"""Analyze this user query and determine what action is needed:

User query: "{message}"

Available actions:
1. csv_only - Query is EXPLICITLY asking to analyze CSV data (e.g., "show statistics", "analyze the data", "what's in the CSV")
2. web_search_only - Query asks for research, information, facts, news, or anything NOT in CSV data (e.g., "research X", "find information about Y", "what is Z", "tell me about")
3. both - Query EXPLICITLY needs both CSV analysis AND web research
4. needs_csv - Query EXPLICITLY asks to analyze a CSV file but none exists

"""
        
        if has_csv_data and csv_columns:
            prompt += f"""A CSV file IS available with columns: {', '.join(csv_columns)}

IMPORTANT: If the query asks to "research", "search", "find information", or asks about topics/companies/facts NOT in the CSV, use web_search_only.
Only use csv_only if the query is clearly about analyzing the uploaded CSV data.
"""
        else:
            prompt += """NO CSV file is uploaded.

IMPORTANT: If the user asks ANY question (research, information, facts, companies, news, etc.), respond with web_search_only.
Only use needs_csv if the query EXPLICITLY asks to analyze a CSV file that doesn't exist.
"""
        
        prompt += """
Respond with ONLY one word: csv_only, web_search_only, both, or needs_csv"""

        # Call Groq to determine intent
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a query router. Analyze the user's query and respond with ONLY one word: csv_only, web_search_only, both, or needs_csv. If the query mentions research, search, or asks for information, use web_search_only."
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
        valid_types = ['csv_only', 'web_search_only', 'both', 'needs_csv']
        for valid_type in valid_types:
            if valid_type in query_type:
                query_type = valid_type
                break
        
        # Safety override: if no CSV and query contains research keywords, force web_search_only
        if not has_csv_data:
            research_keywords = ['research', 'search', 'find', 'look up', 'tell me', 'what is', 'who is', 'information about']
            message_lower = message.lower()
            if any(keyword in message_lower for keyword in research_keywords):
                if query_type != 'web_search_only':
                    print(f"Safety override: forcing web_search_only for research query without CSV")
                    return 'web_search_only'
        
        # Safety override: if query_type is needs_csv but no CSV, default to web_search_only
        if query_type == 'needs_csv' and not has_csv_data:
            print(f"Safety override: needs_csv without CSV, defaulting to web_search_only")
            return 'web_search_only'
        
        return query_type if query_type in valid_types else ('web_search_only' if not has_csv_data else 'csv_only')
            
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
        browserbase_api_key = os.getenv('BROWSERBASE_API_KEY')
        if not browserbase_api_key:
            return None, "BROWSERBASE_API_KEY not configured"
        if not exa_api_key:
            return None, "EXA_API_KEY not configured"
        
        # Get or create research sandbox
        if research_session_id not in research_sandboxes:
            try:
                research_sandbox = E2BSandbox.create(
                    mcp={
                        "exa": {
                            "apiKey": exa_api_key
                        },
                        "browserbase": {
                            "apiKey": browserbase_api_key
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
        
        # Create OpenAI-compatible client for Groq
        groq_openai_client = OpenAI(
            api_key=os.getenv('GROQ_API_KEY'),
            base_url='https://api.groq.com/openai/v1'
        )
        
        research_prompt = f"""{query}

Use Exa to search for recent and relevant information to answer this question comprehensively. 
Provide a detailed summary with sources and key findings."""
        
        print(f"Calling Groq with MCP tools for web research...")
        response = groq_openai_client.chat.completions.create(
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

def detect_competitor_query(message: str, has_company_data: bool) -> Dict:
    """
    Detect if the query is related to competitor analysis
    
    Returns:
        {
            "is_competitor_query": bool,
            "action": "discover" | "scrape" | "compare" | "advantages" | "gaps" | None,
            "confidence": float
        }
    """
    message_lower = message.lower()
    
    # Keywords for different competitor actions
    discover_keywords = ['find competitors', 'discover competitors', 'who are my competitors', 
                        'search for competitors', 'identify competitors', 'list competitors']
    compare_keywords = ['compare with', 'comparison', 'compare to', 'vs', 'versus', 
                       'how do i compare', 'benchmark against']
    advantages_keywords = ['competitive advantage', 'what are my advantages', 'my strengths',
                          'what do i do better', 'unique features', 'what makes us better']
    gaps_keywords = ['feature gaps', 'what am i missing', 'missing features', 
                    'what features do they have', 'what should i add', 'gaps in my product']
    
    # Check for competitor-related keywords
    if any(keyword in message_lower for keyword in discover_keywords):
        return {
            "is_competitor_query": True,
            "action": "discover",
            "confidence": 0.9
        }
    
    if any(keyword in message_lower for keyword in compare_keywords):
        return {
            "is_competitor_query": True,
            "action": "compare",
            "confidence": 0.85
        }
    
    if any(keyword in message_lower for keyword in advantages_keywords):
        return {
            "is_competitor_query": True,
            "action": "advantages",
            "confidence": 0.8
        }
    
    if any(keyword in message_lower for keyword in gaps_keywords):
        return {
            "is_competitor_query": True,
            "action": "gaps",
            "confidence": 0.8
        }
    
    # General competitor mention
    if 'competitor' in message_lower or 'competition' in message_lower:
        return {
            "is_competitor_query": True,
            "action": "compare" if has_company_data else "discover",
            "confidence": 0.6
        }
    
    return {
        "is_competitor_query": False,
        "action": None,
        "confidence": 0.0
    }


@app.route('/api/chat', methods=['POST'])
def chat():
    """Intelligent chat endpoint that routes to CSV analysis, web search, competitor analysis, or combinations"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        print(f"Chat request - session_id: {session_id}, message: {message[:100]}")
        
        # Check if data file is available
        has_csv = session_id in uploaded_files
        csv_columns = None
        file_info = None
        has_company_data = False
        
        if has_csv:
            file_info = uploaded_files[session_id]
            csv_columns = file_info.get('columns_info', {}).get('columns', [])
            has_company_data = file_info.get('is_company_data', False)
        
        # NEW: Check if this is a competitor analysis query
        competitor_detection = detect_competitor_query(message, has_company_data)
        
        if competitor_detection["is_competitor_query"] and competitor_detection["confidence"] > 0.7:
            print(f"🎯 Detected competitor query: action={competitor_detection['action']}")
            
            # Handle competitor analysis queries
            if not has_company_data:
                return jsonify({
                    'response': 'To perform competitor analysis, please first upload your company data (CSV/JSON with company_name, industry, features, pricing).',
                    'error': 'No company data uploaded',
                    'has_research': False
                }), 400
            
            company_data = file_info.get('company_data', {})
            action = competitor_detection["action"]
            
            # Handle different competitor actions
            if action == "discover":
                # Discover competitors
                print("🔍 Routing to competitor discovery...")
                
                company_name = company_data.get('company_name', '')
                industry = company_data.get('industry', '')
                description = company_data.get('description', '')
                
                # Get or create research sandbox
                research_session_id = f"{session_id}_research"
                research_sandbox = None
                
                if research_session_id in research_sandboxes:
                    research_sandbox = research_sandboxes[research_session_id]
                else:
                    exa_api_key = os.getenv('EXA_API_KEY')
                    if not exa_api_key:
                        return jsonify({
                            'response': 'EXA_API_KEY not configured. Please add it to your .env file.',
                            'error': 'Missing API key'
                        }), 500
                    
                    try:
                        research_sandbox = E2BSandbox.create(
                            mcp={"exa": {"apiKey": exa_api_key}}
                        )
                        research_sandboxes[research_session_id] = research_sandbox
                    except Exception as e:
                        return jsonify({
                            'response': f'Failed to create research sandbox: {str(e)}',
                            'error': str(e)
                        }), 500
                
                # Discover competitors
                competitors = discover_competitors(
                    company_name=company_name,
                    industry=industry,
                    description=description,
                    num_results=5,
                    research_sandbox=research_sandbox
                )
                
                if not competitors:
                    return jsonify({
                        'response': f'No competitors found for {company_name} in {industry}. Try adjusting your company description or industry.',
                        'has_research': True
                    })
                
                # Store competitors in session
                uploaded_files[session_id]['competitors'] = competitors
                
                # Format response
                response_text = f"Found {len(competitors)} competitors for {company_name}:\n\n"
                for i, comp in enumerate(competitors, 1):
                    response_text += f"{i}. **{comp['name']}** - {comp['url']}\n"
                    if comp.get('description'):
                        response_text += f"   {comp['description']}\n"
                    response_text += "\n"
                
                response_text += "\nYou can now ask me to:\n"
                response_text += "- Compare with these competitors\n"
                response_text += "- Show competitive advantages\n"
                response_text += "- Identify feature gaps\n"
                
                return jsonify({
                    'response': response_text,
                    'competitors': competitors,
                    'has_research': True
                })
            
            elif action == "compare":
                # Compare with competitors
                print("📊 Routing to competitor comparison...")
                
                # Check if we have competitor data
                competitor_data_dict = file_info.get('competitor_data', {})
                
                if not competitor_data_dict:
                    # Check if we have discovered competitors
                    competitors = file_info.get('competitors', [])
                    
                    if not competitors:
                        return jsonify({
                            'response': 'No competitors found. Please ask me to "find competitors" first.',
                            'has_research': False
                        })
                    
                    # Suggest scraping
                    return jsonify({
                        'response': f'I found {len(competitors)} competitors, but I need to scrape their websites first. This may take a few minutes. Would you like me to proceed?',
                        'competitors': competitors,
                        'needs_scraping': True
                    })
                
                # Generate comparison
                competitors_data = list(competitor_data_dict.values())
                comparison = generate_comparison_table(company_data, competitors_data)
                
                # Store comparison
                uploaded_files[session_id]['comparison'] = comparison
                
                # Format response
                response_text = f"## Competitive Analysis: {company_data.get('company_name')}\n\n"
                response_text += f"Compared with {len(competitors_data)} competitors\n\n"
                
                # Add advantages
                if comparison.get('advantages'):
                    response_text += "### ✅ Competitive Advantages:\n"
                    for adv in comparison['advantages'][:5]:
                        response_text += f"- {adv}\n"
                    response_text += "\n"
                
                # Add gaps
                if comparison.get('gaps'):
                    response_text += "### ⚠️ Feature Gaps:\n"
                    for gap in comparison['gaps'][:5]:
                        response_text += f"- {gap}\n"
                    response_text += "\n"
                
                # Add insights
                if comparison.get('insights'):
                    response_text += "### 💡 Strategic Insights:\n"
                    response_text += comparison['insights']
                
                return jsonify({
                    'response': response_text,
                    'comparison': comparison,
                    'has_research': True
                })
            
            elif action == "advantages":
                # Show competitive advantages
                print("✅ Routing to advantages analysis...")
                
                competitor_data_dict = file_info.get('competitor_data', {})
                
                if not competitor_data_dict:
                    return jsonify({
                        'response': 'I need competitor data to identify advantages. Please ask me to "find competitors" and then "compare with competitors" first.',
                        'has_research': False
                    })
                
                # Get or generate comparison
                comparison = file_info.get('comparison')
                if not comparison:
                    competitors_data = list(competitor_data_dict.values())
                    comparison = generate_comparison_table(company_data, competitors_data)
                    uploaded_files[session_id]['comparison'] = comparison
                
                advantages = comparison.get('advantages', [])
                
                if not advantages:
                    response_text = f"Based on the analysis, {company_data.get('company_name')} doesn't have unique features compared to competitors. Consider developing distinctive capabilities."
                else:
                    response_text = f"## Competitive Advantages for {company_data.get('company_name')}:\n\n"
                    for i, adv in enumerate(advantages, 1):
                        response_text += f"{i}. {adv}\n"
                
                return jsonify({
                    'response': response_text,
                    'advantages': advantages,
                    'has_research': True
                })
            
            elif action == "gaps":
                # Show feature gaps
                print("⚠️ Routing to gaps analysis...")
                
                competitor_data_dict = file_info.get('competitor_data', {})
                
                if not competitor_data_dict:
                    return jsonify({
                        'response': 'I need competitor data to identify gaps. Please ask me to "find competitors" and then "compare with competitors" first.',
                        'has_research': False
                    })
                
                # Get or generate comparison
                comparison = file_info.get('comparison')
                if not comparison:
                    competitors_data = list(competitor_data_dict.values())
                    comparison = generate_comparison_table(company_data, competitors_data)
                    uploaded_files[session_id]['comparison'] = comparison
                
                gaps = comparison.get('gaps', [])
                
                if not gaps:
                    response_text = f"{company_data.get('company_name')} has feature parity with competitors. Great job!"
                else:
                    response_text = f"## Feature Gaps for {company_data.get('company_name')}:\n\n"
                    response_text += "Consider adding these features that competitors offer:\n\n"
                    for i, gap in enumerate(gaps, 1):
                        response_text += f"{i}. {gap}\n"
                
                return jsonify({
                    'response': response_text,
                    'gaps': gaps,
                    'has_research': True
                })
        
        # If not a competitor query, proceed with existing logic
        # Use LLM to determine what type of query this is
        query_type = determine_query_type_with_llm(message, has_csv_data=has_csv, csv_columns=csv_columns)
        print(f"Query type determined by LLM: {query_type}")
        
        # Handle different query types
        # If needs_csv but no CSV, default to web_search_only (allow any query without CSV)
        if query_type == 'needs_csv' and not has_csv:
            print(f"Overriding needs_csv to web_search_only (no CSV uploaded, allowing web search)")
            query_type = 'web_search_only'
        
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
                    'error': 'Please upload a data file (CSV, XLS, or Excel) first',
                    'session_id': session_id
                }), 400
            
            try:
                file_info = uploaded_files[session_id]
                sbx = get_or_create_sandbox(session_id)
                
                # Create prompt for Groq
                columns_info = file_info.get('columns_info', {})
                columns_list = columns_info.get('columns', [])
                
                # If both data file and web search, incorporate web research context
                context_note = ""
                if query_type == 'both' and web_research_result:
                    context_note = f"\n\nIMPORTANT: The user also asked for web research. Here's what was found:\n{web_research_result}\n\nYou can use this context to enhance your analysis, but focus on analyzing the data file."
                
                file_type = file_info.get('file_type', 'csv')
                file_type_name = 'Excel' if file_type == 'excel' else 'CSV'
                filename = file_info['filename']
                
                # Build sheet information for Excel files
                sheet_info_text = ""
                if file_type == 'excel':
                    sheet_names = columns_info.get('sheet_names', [])
                    sheets_info = columns_info.get('sheets', {})
                    
                    if sheet_names and len(sheet_names) > 1:
                        # Multiple sheets - provide detailed information
                        sheet_info_text = f"\n\nIMPORTANT: This Excel file contains {len(sheet_names)} sheets:\n"
                        for sheet_name in sheet_names:
                            sheet_data = sheets_info.get(sheet_name, {})
                            sheet_cols = sheet_data.get('columns', [])
                            sheet_shape = sheet_data.get('shape', [0, 0])
                            sheet_info_text += f"- Sheet '{sheet_name}': {len(sheet_cols)} columns ({', '.join(sheet_cols[:5])}{'...' if len(sheet_cols) > 5 else ''}), {sheet_shape[0]} rows\n"
                        
                        sheet_info_text += f"\nCRITICAL: You MUST choose the appropriate sheet based on the user's query. Analyze the query to determine which sheet contains the relevant data.\n"
                        sheet_names_quoted = ', '.join([f"'{s}'" for s in sheet_names])
                        sheet_info_text += f"Available sheets: {sheet_names_quoted}\n"
                        file_path = file_info['sandbox_path']
                        sheet_info_text += f"To load a specific sheet, use: df = pd.read_excel(\"{file_path}\", sheet_name='SHEET_NAME')\n"
                        sheet_info_text += f"If the user's query doesn't specify a sheet, intelligently choose the most relevant one based on:\n"
                        sheet_info_text += f"  1. Column names that match the query topic\n"
                        sheet_info_text += f"  2. Sheet names that match keywords in the query\n"
                        sheet_info_text += f"  3. The sheet with the most relevant data structure\n"
                        sheet_info_text += f"If unsure, you can load multiple sheets and compare, or ask the user to clarify.\n"
                    elif sheet_names and len(sheet_names) == 1:
                        # Single sheet - just mention it
                        sheet_info_text = f"\n\nThis Excel file has one sheet: '{sheet_names[0]}'\n"
                
                # Determine the correct pandas function to use
                if file_type == 'excel':
                    if columns_info.get('sheet_names') and len(columns_info.get('sheet_names', [])) > 1:
                        # Multiple sheets - use sheet_name parameter
                        default_sheet = columns_info.get('default_sheet', columns_info.get('sheet_names', [''])[0])
                        load_code = f"df = pd.read_excel(\"{file_info['sandbox_path']}\", sheet_name='{default_sheet}')  # Change sheet_name based on user's query"
                    else:
                        load_code = f'df = pd.read_excel("{file_info["sandbox_path"]}")'
                else:
                    load_code = f'df = pd.read_csv("{file_info["sandbox_path"]}")'
                
                system_prompt = f"""You are a data analysis assistant. A {file_type_name} file has been uploaded with the following information:
- Filename: {filename}
- Path in sandbox: {file_info['sandbox_path']}
- File type: {file_type_name} ({file_type})
- Columns: {', '.join(columns_list)}
- Shape: {columns_info.get('shape', 'Unknown')}
{sheet_info_text}{context_note}

When the user asks for analysis, generate Python code to:
1. Load the data file using pandas. The file is a {file_type_name} file, so use:
   {load_code}
2. Perform the requested analysis
3. CRITICAL: Always convert results to strings before printing. For example:
   - For column names: print(list(df.columns)) or print(', '.join(df.columns))
   - For statistics: print(df.describe().to_string())
   - For dataframes: print(df.head().to_string()) or print(df.to_string())
   - For single values: print(str(value))
   - NEVER just print(df.columns) - convert Index to list first: print(list(df.columns))
   - NEVER just print(df) - use .to_string(): print(df.to_string())
4. Create visualizations using matplotlib when appropriate
5. Save plots with: plt.savefig('/home/user/chart.png', bbox_inches='tight', dpi=150)
6. Always end matplotlib code with plt.show() to generate the output

CRITICAL REQUIREMENTS:
- Use proper Python indentation (4 spaces per level)
- All code blocks after if/else/for/while/def must be indented
- Ensure all code is syntactically correct and executable
- Use consistent indentation throughout

Respond with ONLY the Python code wrapped in ```python and ``` markers, no explanations before or after.
Make sure to import necessary libraries (pandas, matplotlib.pyplot, numpy, etc.).
CRITICAL: Always include print() statements to output results, especially for statistics and data summaries."""

                # Call Groq for code generation
                print("Calling Groq to generate code...")
                groq_response = groq_client.chat.completions.create(
                    model="qwen/qwen3-32b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.1,
                    max_tokens=2048
                )
                response_text = groq_response.choices[0].message.content
                csv_code = extract_code_from_response(response_text)
                
                if not csv_code:
                    csv_error = "No code was generated from the response"
                    print(f"CSV analysis error: {csv_error}")
                    if query_type == 'csv_only':
                        return jsonify({
                            'error': csv_error,
                            'has_code': False
                        }), 500
                else:
                    print(f"Generated code ({len(csv_code)} chars), validating syntax...")
                    # Validate code syntax
                    try:
                        compile(csv_code, '<string>', 'exec')
                    except SyntaxError as e:
                        csv_error = f"Syntax error: {e.msg} on line {e.lineno}"
                        print(f"CSV analysis error: {csv_error}")
                        if query_type == 'csv_only':
                            return jsonify({
                                'response': csv_error,
                                'code': csv_code,
                                'has_code': True,
                                'error': True
                            })
                    else:
                        # Execute code in sandbox
                        print("Executing code in sandbox...")
                        execution = sbx.run_code(csv_code)
                        
                        if execution.error:
                            csv_error = f"Execution error: {execution.error.name}: {execution.error.value}"
                            print(f"CSV analysis error: {csv_error}")
                            if query_type == 'csv_only':
                                return jsonify({
                                    'response': csv_error,
                                    'code': csv_code,
                                    'has_code': True,
                                    'error': True
                                })
                        else:
                            # Capture stdout/stderr
                            if hasattr(execution, 'logs'):
                                if hasattr(execution.logs, 'stdout') and execution.logs.stdout:
                                    stdout_text = ''.join(execution.logs.stdout).strip()
                                    if stdout_text:
                                        csv_execution_output.append(stdout_text)
                                        print(f"Captured stdout: {stdout_text[:200]}")
                                
                                if hasattr(execution.logs, 'stderr') and execution.logs.stderr:
                                    stderr_text = ''.join(execution.logs.stderr).strip()
                                    if stderr_text:
                                        csv_execution_output.append(f"STDERR: {stderr_text}")
                            
                            # Process results for charts
                            for result in execution.results:
                                if hasattr(result, 'png') and result.png:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    chart_filename = f"chart_{session_id}_{timestamp}.png"
                                    chart_path = CHARTS_DIR / chart_filename
                                    
                                    with open(chart_path, 'wb') as f:
                                        f.write(base64.b64decode(result.png))
                                    
                                    csv_charts.append({
                                        'filename': chart_filename,
                                        'url': f'/api/chart/{chart_filename}'
                                    })
                                    print(f"Saved chart: {chart_filename}")
                            
                            # Generate explanation
                            results_summary = '\n'.join(csv_execution_output) if csv_execution_output else 'Analysis completed.'
                            print(f"Generating explanation for CSV analysis...")
                            try:
                                explanation_prompt = f"""Based on this data analysis code and results, provide a brief, clear explanation:

Code executed:
{csv_code}

Results:
{results_summary}

Provide a concise 2-3 sentence explanation of the analysis and findings."""

                                explanation_response = groq_client.chat.completions.create(
                                    model="qwen/qwen3-32b",
                                    messages=[
                                        {"role": "system", "content": "You are a data analysis expert. Explain results clearly and concisely."},
                                        {"role": "user", "content": explanation_prompt}
                                    ],
                                    temperature=0.3,
                                    max_tokens=512
                                )
                                csv_analysis_result = explanation_response.choices[0].message.content
                                print(f"CSV analysis completed successfully")
                            except Exception as e:
                                print(f"Error generating explanation: {e}")
                                csv_analysis_result = f"Analysis completed. Results:\n{results_summary[:500]}"
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
    
    # Try to find code block with python marker
    pattern = r'```python\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
    # Try to find any code block
    pattern = r'```\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code = matches[0].strip()
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
    # If no code blocks, check if entire response looks like code
    if 'import' in text and ('pandas' in text or 'matplotlib' in text):
        code = text.strip()
        # Fix indentation
        code = fix_code_indentation(code)
        return code
    
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
        
        # Create OpenAI-compatible client for Groq
        groq_openai_client = OpenAI(
            api_key=os.getenv('GROQ_API_KEY'),
            base_url='https://api.groq.com/openai/v1'
        )
        
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
            response = groq_openai_client.chat.completions.create(
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

@app.route('/api/competitor/discover', methods=['POST'])
def discover_competitors_endpoint():
    """Discover competitors using Exa MCP"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        
        print(f"Competitor discovery request - session_id: {session_id}")
        
        # Check if company data exists in session
        if session_id not in uploaded_files:
            return jsonify({
                'error': 'No company data found. Please upload company data first.',
                'session_id': session_id
            }), 400
        
        file_info = uploaded_files[session_id]
        
        # Check if this is company data
        if not file_info.get('is_company_data', False):
            return jsonify({
                'error': 'Uploaded file is not company data. Please upload a file with company information.',
                'session_id': session_id
            }), 400
        
        company_data = file_info.get('company_data', {})
        
        # Extract company information
        company_name = company_data.get('company_name', '')
        industry = company_data.get('industry', '')
        description = company_data.get('description', '')
        
        if not company_name or not industry:
            return jsonify({
                'error': 'Company name and industry are required for competitor discovery',
                'session_id': session_id
            }), 400
        
        print(f"Discovering competitors for: {company_name} in {industry}")
        
        # Get or create research sandbox (reuse existing if available)
        research_session_id = f"{session_id}_research"
        research_sandbox = None
        
        if research_session_id in research_sandboxes:
            research_sandbox = research_sandboxes[research_session_id]
            print(f"Reusing existing research sandbox")
        else:
            # Create new sandbox with Exa MCP
            exa_api_key = os.getenv('EXA_API_KEY')
            if not exa_api_key:
                return jsonify({
                    'error': 'EXA_API_KEY not configured. Please add it to your .env file.'
                }), 500
            
            try:
                print(f"Creating new MCP-enabled sandbox with Exa...")
                research_sandbox = E2BSandbox.create(
                    mcp={"exa": {"apiKey": exa_api_key}}
                )
                research_sandboxes[research_session_id] = research_sandbox
                print(f"Research sandbox created successfully")
            except Exception as e:
                print(f"Error creating research sandbox: {e}")
                return jsonify({
                    'error': f'Failed to create research sandbox: {str(e)}'
                }), 500
        
        # Call competitor discovery service
        try:
            competitors = discover_competitors(
                company_name=company_name,
                industry=industry,
                description=description,
                num_results=5,
                research_sandbox=research_sandbox
            )
            
            if not competitors:
                return jsonify({
                    'success': True,
                    'competitors': [],
                    'message': 'No competitors found. Try adjusting your company description or industry.',
                    'session_id': session_id
                })
            
            # Store competitors in session
            uploaded_files[session_id]['competitors'] = competitors
            
            print(f"✅ Discovered {len(competitors)} competitors")
            
            return jsonify({
                'success': True,
                'competitors': competitors,
                'count': len(competitors),
                'session_id': session_id
            })
            
        except Exception as e:
            print(f"Error discovering competitors: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'Competitor discovery failed: {str(e)}',
                'session_id': session_id
            }), 500
    
    except Exception as e:
        print(f"Error in discover_competitors endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitor/scrape', methods=['POST'])
def scrape_competitor_endpoint():
    """Scrape competitor website using Browserbase MCP"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        competitor_url = data.get('url', '')
        
        print(f"Competitor scraping request - session_id: {session_id}, url: {competitor_url}")
        
        if not competitor_url:
            return jsonify({
                'error': 'URL is required for scraping',
                'session_id': session_id
            }), 400
        
        # Validate URL format
        if not competitor_url.startswith(('http://', 'https://')):
            competitor_url = 'https://' + competitor_url
        
        # Import validation function
        from scrapers.browserbase_mcp import validate_url
        
        is_valid, error_msg = validate_url(competitor_url)
        if not is_valid:
            return jsonify({
                'error': f'Invalid URL: {error_msg}',
                'session_id': session_id,
                'url': competitor_url
            }), 400
        
        # Get or create Browserbase sandbox using unified manager
        try:
            browserbase_sandbox = get_or_create_browserbase_sandbox(session_id)
        except Exception as e:
            print(f"Error creating Browserbase sandbox: {e}")
            return jsonify({
                'error': f'Failed to create Browserbase sandbox: {str(e)}. Please check BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in .env'
            }), 500
        
        # Scrape competitor pages
        try:
            from datetime import datetime
            
            print(f"Starting scraping for {competitor_url}...")
            scraped_pages = scrape_competitor_pages(browserbase_sandbox, competitor_url)
            
            # Add timestamp
            scraped_pages['timestamp'] = datetime.now().isoformat()
            
            # Extract data from scraped pages
            print(f"Extracting data from scraped pages...")
            competitor_data = extract_all_competitor_data(scraped_pages, competitor_url)
            
            # Store competitor data in session
            if session_id in uploaded_files:
                if 'competitor_data' not in uploaded_files[session_id]:
                    uploaded_files[session_id]['competitor_data'] = {}
                
                # Store by URL
                uploaded_files[session_id]['competitor_data'][competitor_url] = competitor_data
                
                print(f"✅ Stored competitor data for {competitor_url}")
            
            return jsonify({
                'success': True,
                'competitor_data': competitor_data,
                'scraping_status': scraped_pages.get('status', 'unknown'),
                'session_id': session_id,
                'url': competitor_url
            })
            
        except Exception as e:
            print(f"Error scraping competitor: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'Scraping failed: {str(e)}',
                'session_id': session_id,
                'url': competitor_url
            }), 500
    
    except Exception as e:
        print(f"Error in scrape_competitor endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitor/compare', methods=['POST'])
def compare_competitors_endpoint():
    """Generate comparison table between company and competitors"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        
        print(f"Competitor comparison request - session_id: {session_id}")
        
        # Check if company data exists in session
        if session_id not in uploaded_files:
            return jsonify({
                'error': 'No company data found. Please upload company data first.',
                'session_id': session_id
            }), 400
        
        file_info = uploaded_files[session_id]
        
        # Check if this is company data
        if not file_info.get('is_company_data', False):
            return jsonify({
                'error': 'Uploaded file is not company data. Please upload a file with company information.',
                'session_id': session_id
            }), 400
        
        company_data = file_info.get('company_data', {})
        
        # Get competitor data from session
        competitor_data_dict = file_info.get('competitor_data', {})
        
        if not competitor_data_dict:
            return jsonify({
                'error': 'No competitor data found. Please scrape competitors first using /api/competitor/scrape',
                'session_id': session_id
            }), 400
        
        # Convert competitor data dict to list
        competitors_data = list(competitor_data_dict.values())
        
        print(f"Comparing {company_data.get('company_name')} with {len(competitors_data)} competitors")
        
        # Generate comparison table
        try:
            comparison = generate_comparison_table(company_data, competitors_data)
            
            # Store comparison in session
            uploaded_files[session_id]['comparison'] = comparison
            
            print(f"✅ Comparison generated successfully")
            
            return jsonify({
                'success': True,
                'comparison': comparison,
                'session_id': session_id
            })
            
        except Exception as e:
            print(f"Error generating comparison: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'Comparison generation failed: {str(e)}',
                'session_id': session_id
            }), 500
    
    except Exception as e:
        print(f"Error in compare_competitors endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

