import os
import base64
import json
import atexit
import signal
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
from e2b import Sandbox as E2BSandbox
from groq import Groq
from openai import OpenAI

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

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload CSV file to sandbox"""
    try:
        print(f"Upload request received")
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', 'default')
        print(f"Uploading file: {file.filename}, session_id: {session_id}")
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are allowed'}), 400
        
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
        
        # Analyze CSV to get column info (optimized for large files)
        print("Running analysis code to extract column info...")
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
                'warning': 'Could not analyze CSV structure automatically'
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
                'columns_info': columns_info
            }
            
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

def determine_query_type_with_llm(message, has_csv_data=False, csv_columns=None):
    """Use LLM to determine if query needs CSV analysis, web search, or both"""
    try:
        # Build context for LLM
        context = f"""User query: "{message}"

Available capabilities:
1. CSV Data Analysis: Analyze uploaded CSV files, generate statistics, create visualizations
2. Web Research: Search the web for current information, news, facts, and research

"""
        
        if has_csv_data and csv_columns:
            context += f"""CSV file is available with columns: {', '.join(csv_columns)}

You can analyze this CSV data OR search the web, OR do both if the query requires it.
"""
        else:
            context += "No CSV file is currently uploaded. You can only perform web research.\n"
        
        context += """
Based on the user's query, determine what action(s) are needed:
- "csv_only": Query is about analyzing the CSV data
- "web_search_only": Query requires web search (no CSV analysis needed)
- "both": Query needs both CSV analysis AND web research
- "needs_csv": Query seems to expect CSV data but none is uploaded

Respond with ONLY one of these exact strings: csv_only, web_search_only, both, or needs_csv"""

        # Call LLM to determine intent
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are an intelligent routing assistant. Analyze user queries and determine what capabilities are needed. Respond with only the action type: csv_only, web_search_only, both, or needs_csv"
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        query_type = response.choices[0].message.content.strip().lower()
        
        # Validate and normalize response
        valid_types = ['csv_only', 'web_search_only', 'both', 'needs_csv']
        if query_type in valid_types:
            return query_type
        
        # Fallback logic if LLM returns something unexpected
        if 'csv' in query_type and 'web' in query_type:
            return 'both'
        elif 'csv' in query_type:
            return 'csv_only' if has_csv_data else 'needs_csv'
        elif 'web' in query_type or 'search' in query_type:
            return 'web_search_only'
        else:
            # Default: if CSV exists, try CSV analysis; otherwise web search
            return 'csv_only' if has_csv_data else 'web_search_only'
            
    except Exception as e:
        print(f"Error in LLM-based query type determination: {e}")
        # Fallback: if CSV exists, default to CSV analysis
        return 'csv_only' if has_csv_data else 'web_search_only'

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
                    },
                    timeout_ms=600_000
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

@app.route('/api/chat', methods=['POST'])
def chat():
    """Intelligent chat endpoint that routes to CSV analysis, web search, or both"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        print(f"Chat request - session_id: {session_id}, message: {message[:100]}")
        
        # Check if CSV data is available
        has_csv = session_id in uploaded_files
        csv_columns = None
        file_info = None
        
        if has_csv:
            file_info = uploaded_files[session_id]
            csv_columns = file_info.get('columns_info', {}).get('columns', [])
        
        # Use LLM to determine what type of query this is
        query_type = determine_query_type_with_llm(message, has_csv_data=has_csv, csv_columns=csv_columns)
        print(f"Query type determined by LLM: {query_type}")
        
        # Handle different query types
        if query_type == 'needs_csv' and not has_csv:
            return jsonify({
                'error': 'Please upload a CSV file first, or ask a web search question.',
                'session_id': session_id
            }), 400
        
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
                    'error': 'Please upload a CSV file first',
                    'session_id': session_id
                }), 400
            
            try:
                file_info = uploaded_files[session_id]
                sbx = get_or_create_sandbox(session_id)
                
                # Create prompt for Groq
                columns_info = file_info.get('columns_info', {})
                columns_list = columns_info.get('columns', [])
                
                # If both CSV and web search, incorporate web research context
                context_note = ""
                if query_type == 'both' and web_research_result:
                    context_note = f"\n\nIMPORTANT: The user also asked for web research. Here's what was found:\n{web_research_result}\n\nYou can use this context to enhance your analysis, but focus on analyzing the CSV data."
                
                system_prompt = f"""You are a data analysis assistant. A CSV file has been uploaded with the following information:
- Filename: {file_info['filename']}
- Path in sandbox: {file_info['sandbox_path']}
- Columns: {', '.join(columns_list)}
- Shape: {columns_info.get('shape', 'Unknown')}
{context_note}

When the user asks for analysis, generate Python code to:
1. Load the CSV using pandas from the path: {file_info['sandbox_path']}
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
            return jsonify({
                'response': web_research_result or "Web search completed but no results returned.",
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
                    },
                    timeout_ms=600_000  # 10 minutes
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

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

