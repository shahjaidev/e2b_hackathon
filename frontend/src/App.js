import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [sessionId] = useState(() => `session_${Date.now()}`);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileUpload = async (file) => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);

    setIsLoading(true);
    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Store session_id with the uploaded file data (use the one from response if available)
      const fileData = { 
        ...response.data, 
        session_id: response.data.session_id || sessionId 
      };
      setUploadedFile(fileData);
      console.log('File uploaded with session_id:', fileData.session_id);
      setMessages([
        {
          type: 'system',
          content: `File "${response.data.filename}" uploaded successfully.

Dataset info:
Rows: ${response.data.columns_info?.shape?.[0] || 'N/A'}
Columns: ${response.data.columns_info?.shape?.[1] || 'N/A'}
Column names: ${response.data.columns_info?.columns?.join(', ') || 'N/A'}

You can now ask questions about your data.`,
        },
      ]);
    } catch (error) {
      setMessages([
        {
          type: 'error',
          content: `Error uploading file: ${error.response?.data?.error || error.message}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.csv')) {
      handleFileUpload(file);
    } else {
      alert('Please upload a CSV file');
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;
    if (!uploadedFile) {
      alert('Please upload a CSV file first');
      return;
    }

    const userMessage = inputMessage;
    setInputMessage('');
    setMessages((prev) => [...prev, { type: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // Use the session_id from uploadedFile if available, otherwise use the component's sessionId
      const activeSessionId = uploadedFile?.session_id || sessionId;
      console.log('Sending chat request with session_id:', activeSessionId);
      const response = await axios.post('/api/chat', {
        message: userMessage,
        session_id: activeSessionId,
      });

      const botMessage = {
        type: 'bot',
        content: response.data.response,
        code: response.data.code,
        charts: response.data.charts,
        execution_output: response.data.execution_output,
        error: response.data.error,
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      const errorMessage = error.response?.data?.error || error.message;
      
      // If the error is about missing file, try to re-upload
      if (errorMessage.includes('upload a CSV file first') && uploadedFile) {
        setMessages((prev) => [
          ...prev,
          {
            type: 'error',
            content: `Session expired. Please re-upload your file.`,
          },
        ]);
        // Optionally auto-clear the uploaded file state
        // setUploadedFile(null);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            type: 'error',
            content: `Error: ${errorMessage}`,
          },
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const suggestedQuestions = [
    "Show me the distribution of values in the first column",
    "What are the summary statistics of the numerical columns?",
    "Create a correlation heatmap",
    "Show the top 10 rows by the first numerical column",
  ];

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1>CSV Analyzer</h1>
          <p>Upload your CSV and ask questions — powered by Groq & E2B</p>
        </header>

        {!uploadedFile ? (
          <div
            className={`upload-area ${isDragging ? 'dragging' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="upload-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            </div>
            <h2>Upload Your CSV File</h2>
            <p>Drag and drop or click to browse</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileInputChange}
              style={{ display: 'none' }}
            />
          </div>
        ) : (
          <div className="chat-container">
            <div className="file-info">
              <span className="file-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
              </span>
              <span className="file-name">{uploadedFile.filename}</span>
              <button
                className="change-file-btn"
                onClick={() => {
                  setUploadedFile(null);
                  setMessages([]);
                  fileInputRef.current?.click();
                }}
              >
                Change File
              </button>
            </div>

            <div className="messages">
              {messages.map((msg, idx) => (
                <div key={idx} className={`message message-${msg.type}`}>
                  <div className="message-content">
                    {msg.type === 'user' && (
                      <div className="message-icon user-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                          <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                      </div>
                    )}
                    {msg.type === 'bot' && (
                      <div className="message-icon bot-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="11" width="18" height="10" rx="2" ry="2"></rect>
                          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                      </div>
                    )}
                    {msg.type === 'system' && (
                      <div className="message-icon system-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="16" x2="12" y2="12"></line>
                          <line x1="12" y1="8" x2="12.01" y2="8"></line>
                        </svg>
                      </div>
                    )}
                    {msg.type === 'error' && (
                      <div className="message-icon error-icon">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="8" x2="12" y2="12"></line>
                          <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                      </div>
                    )}
                    
                    <div className="message-text">
                      <pre>{msg.content}</pre>
                      
                      {msg.code && (
                        <div className="code-block">
                          <div className="code-header">Generated Code:</div>
                          <pre><code>{msg.code}</code></pre>
                        </div>
                      )}
                      
                      {msg.execution_output && msg.execution_output.length > 0 && (
                        <div className="output-block">
                          <div className="output-header">Output:</div>
                          <pre>{msg.execution_output.join('\n')}</pre>
                        </div>
                      )}
                      
                      {msg.charts && msg.charts.map((chart, i) => (
                        <div key={i} className="chart-container">
                          <img src={chart.url} alt={`Chart ${i + 1}`} />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="message message-bot">
                  <div className="message-content">
                    <div className="message-icon bot-icon">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="3" y="11" width="18" height="10" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                      </svg>
                    </div>
                    <div className="message-text">
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {messages.length === 1 && (
              <div className="suggested-questions">
                <p>Try asking:</p>
                {suggestedQuestions.map((question, idx) => (
                  <button
                    key={idx}
                    className="suggestion-btn"
                    onClick={() => setInputMessage(question)}
                  >
                    {question}
                  </button>
                ))}
              </div>
            )}

            <form className="input-form" onSubmit={handleSendMessage}>
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask a question about your data..."
                disabled={isLoading}
              />
              <button type="submit" disabled={isLoading || !inputMessage.trim()}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

