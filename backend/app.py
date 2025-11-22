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
from groq import Groq

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

def cleanup_all_sandboxes():
    """Cleanup all active sandboxes"""
    print("Cleaning up all sandboxes...")
    for session_id, sandbox in list(active_sandboxes.items()):
        try:
            sandbox.close()
            print(f"Closed sandbox for session: {session_id}")
        except Exception as e:
            print(f"Error closing sandbox {session_id}: {e}")
    active_sandboxes.clear()
    uploaded_files.clear()

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
            sandbox.close()
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
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.form.get('session_id', 'default')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'Only CSV files are allowed'}), 400
        
        # Save file locally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{file.filename}"
        filepath = UPLOAD_DIR / filename
        file.save(filepath)
        
        # Upload to sandbox
        sbx = get_or_create_sandbox(session_id)
        with open(filepath, 'rb') as f:
            sandbox_path = sbx.files.write(f"/home/user/{file.filename}", f)
        
        # Analyze CSV to get column info
        analysis_code = f"""
import pandas as pd
df = pd.read_csv("{sandbox_path.path}")
columns_info = {{
    'columns': list(df.columns),
    'shape': df.shape,
    'dtypes': df.dtypes.astype(str).to_dict(),
    'sample': df.head(3).to_dict(orient='records')
}}
columns_info
"""
        
        result = sbx.run_code(analysis_code)
        
        # Extract the actual dictionary value from the result
        columns_info = {}
        if result.results and len(result.results) > 0:
            import ast
            try:
                # Get the text representation of the result (e2b returns dict as string)
                result_obj = result.results[0]
                if hasattr(result_obj, 'text') and result_obj.text:
                    # Parse the string representation of the dict
                    result_text = result_obj.text.strip()
                    # Remove any leading/trailing whitespace and parse
                    columns_info = ast.literal_eval(result_text)
                else:
                    # Fallback: try to convert to string and parse
                    result_text = str(result_obj).strip()
                    if result_text.startswith('{'):
                        columns_info = ast.literal_eval(result_text)
            except (ValueError, SyntaxError, AttributeError) as e:
                # If parsing fails, return empty dict with basic structure
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
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'sandbox_path': sandbox_path.path,
            'columns_info': columns_info,
            'session_id': session_id  # Return session_id so frontend can use it
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages and execute code if needed"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        # Debug: log session info
        print(f"Chat request - session_id: {session_id}, uploaded_files keys: {list(uploaded_files.keys())}")
        
        # If session not found, try to use 'default' as fallback
        if session_id not in uploaded_files:
            # Try default session as fallback
            if 'default' in uploaded_files and len(uploaded_files) == 1:
                print(f"Using default session as fallback for {session_id}")
                session_id = 'default'
            else:
                # Try to find any session with files (fallback for debugging)
                if uploaded_files:
                    print(f"Session {session_id} not found. Available sessions: {list(uploaded_files.keys())}")
                return jsonify({
                    'error': 'Please upload a CSV file first',
                    'session_id': session_id,
                    'available_sessions': list(uploaded_files.keys())
                }), 400
        
        file_info = uploaded_files[session_id]
        sbx = get_or_create_sandbox(session_id)
        
        # Create prompt for Groq
        columns_info = file_info.get('columns_info', {})
        columns_list = columns_info.get('columns', [])
        
        system_prompt = f"""You are a data analysis assistant. A CSV file has been uploaded with the following information:
- Filename: {file_info['filename']}
- Path in sandbox: {file_info['sandbox_path']}
- Columns: {', '.join(columns_list)}
- Shape: {columns_info.get('shape', 'Unknown')}

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

Example of CORRECT indentation:
```python
if condition:
    # This line is indented with 4 spaces
    result = do_something()
    print(result)
else:
    # This else block is also properly indented
    print("No result")
```

Respond with ONLY the Python code wrapped in ```python and ``` markers, no explanations before or after.
Make sure to import necessary libraries (pandas, matplotlib.pyplot, numpy, etc.).
CRITICAL: Always include print() statements to output results, especially for statistics and data summaries."""

        # Call Groq
        try:
            groq_response = groq_client.chat.completions.create(
                model="qwen/qwen3-32b",  # Qwen 3 32B model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.1,
                max_tokens=2048
            )
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            return jsonify({
                'error': f'Error generating code: {str(e)}',
                'has_code': False
            }), 500
        response_text = groq_response.choices[0].message.content
        
        # Extract code from response
        code = extract_code_from_response(response_text)
        
        if not code:
            return jsonify({
                'response': response_text,
                'has_code': False
            })
        
        # Validate code syntax before execution
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            print(f"Syntax error in generated code: {e}")
            # Try to fix common issues and re-validate
            # If still fails, return error with code
            return jsonify({
                'response': f"Generated code has a syntax error: {e.msg} on line {e.lineno}\n\nPlease try rephrasing your question.",
                'code': code,
                'has_code': True,
                'error': True,
                'syntax_error': True
            })
        
        # Execute code in sandbox
        execution = sbx.run_code(code)
        
        # Handle execution results
        execution_output = []
        charts = []
        
        if execution.error:
            return jsonify({
                'response': f"Error executing code:\n{execution.error.name}: {execution.error.value}",
                'code': code,
                'has_code': True,
                'error': True
            })
        
        # Capture stdout/stderr from logs (this is where print() output goes)
        if hasattr(execution, 'logs'):
            if hasattr(execution.logs, 'stdout') and execution.logs.stdout:
                # stdout is a list of strings
                stdout_text = ''.join(execution.logs.stdout).strip()
                if stdout_text:
                    execution_output.append(stdout_text)
                    print(f"Captured stdout: {stdout_text[:200]}")
            
            if hasattr(execution.logs, 'stderr') and execution.logs.stderr:
                stderr_text = ''.join(execution.logs.stderr).strip()
                if stderr_text:
                    execution_output.append(f"STDERR: {stderr_text}")
        
        # Also check execution.text if available
        if hasattr(execution, 'text') and execution.text:
            text_output = str(execution.text).strip()
            if text_output and text_output not in execution_output:
                execution_output.append(text_output)
        
        # Process results for charts and other outputs
        for idx, result in enumerate(execution.results):
            # Check for text in results (for return values, etc.)
            if hasattr(result, 'text') and result.text:
                text_output = str(result.text).strip()
                if text_output and text_output not in execution_output:
                    execution_output.append(text_output)
            
            # Check for PNG charts
            if hasattr(result, 'png') and result.png:
                # Save chart
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                chart_filename = f"chart_{session_id}_{timestamp}.png"
                chart_path = CHARTS_DIR / chart_filename
                
                with open(chart_path, 'wb') as f:
                    f.write(base64.b64decode(result.png))
                
                charts.append({
                    'filename': chart_filename,
                    'url': f'/api/chart/{chart_filename}'
                })
                print(f"Saved chart: {chart_filename}")
        
        # Prepare results summary for explanation
        results_summary = '\n'.join(execution_output) if execution_output else 'No text output generated.'
        if charts:
            results_summary += f'\n{len(charts)} chart(s) generated.'
        
        # Generate explanation with timeout handling
        try:
            explanation_prompt = f"""Based on this data analysis code and results, provide a brief, clear explanation of what was found:

Code executed:
{code}

Results:
{results_summary}

Provide a concise 2-3 sentence explanation of the analysis and findings. If results show statistics, mention key numbers."""

            explanation_response = groq_client.chat.completions.create(
                model="qwen/qwen3-32b",
                messages=[
                    {"role": "system", "content": "You are a data analysis expert. Explain results clearly and concisely."},
                    {"role": "user", "content": explanation_prompt}
                ],
                temperature=0.3,
                max_tokens=512
            )
            
            explanation_text = explanation_response.choices[0].message.content
        except Exception as e:
            print(f"Error generating explanation: {e}")
            # Fallback explanation if AI explanation fails
            if execution_output:
                explanation_text = f"Analysis completed. Results:\n{results_summary[:500]}"
            elif charts:
                explanation_text = f"Analysis completed. {len(charts)} chart(s) generated."
            else:
                explanation_text = "Code executed successfully, but no output was generated."
        
        return jsonify({
            'response': explanation_text,
            'code': code,
            'execution_output': execution_output,
            'charts': charts,
            'has_code': True,
            'error': False
        })
    
    except Exception as e:
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
    """Fix common indentation issues in Python code - specifically missing indentation after colons"""
    lines = code.split('\n')
    fixed_lines = []
    indent_level = 0
    indent_size = 4
    
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        original_indent = len(line) - len(stripped)
        
        # Skip empty lines and comments (preserve them)
        if not stripped or stripped.startswith('#'):
            fixed_lines.append(line)
            continue
        
        # Check if previous line ended with ':' and requires indentation
        if i > 0 and len(fixed_lines) > 0:
            prev_stripped = fixed_lines[-1].strip()
            if prev_stripped.endswith(':') and not prev_stripped.startswith('#'):
                # Previous line was a control structure that needs indented block
                keywords = ['if ', 'for ', 'while ', 'def ', 'try:', 'with ', 'class ', 'elif ', 'except ']
                if any(prev_stripped.startswith(kw) for kw in keywords):
                    # Current line should be indented, but check if it already is
                    expected_indent = indent_level + indent_size
                    if original_indent < expected_indent:
                        # Line is not indented enough - fix it
                        fixed_lines.append(' ' * expected_indent + stripped)
                        # Update indent level for next iteration
                        indent_level = expected_indent // indent_size
                        continue
        
        # Handle dedent keywords (elif, else, except, finally)
        if stripped.startswith(('elif ', 'else:', 'except ', 'finally:')):
            indent_level = max(0, indent_level - 1)
        
        # Apply current indent level
        fixed_lines.append(' ' * (indent_level * indent_size) + stripped)
        
        # Check if this line increases indent for next line
        if stripped.endswith(':') and not stripped.startswith('#'):
            keywords = ['if ', 'for ', 'while ', 'def ', 'try:', 'with ', 'class ']
            if any(stripped.startswith(kw) for kw in keywords):
                indent_level += 1
    
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

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

