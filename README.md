# 🤖 CSV Analyzer AI Assistant

An intelligent AI assistant that analyzes CSV files using **Gemini AI** for natural language understanding and **E2B** for secure Python code execution in sandboxed environments.

## ✨ Features

- 📊 **CSV Upload & Analysis**: Drag-and-drop CSV files for instant analysis
- 💬 **Natural Language Queries**: Ask questions in plain English about your data
- 🐍 **Python Code Execution**: AI generates and executes Python code in E2B sandbox
- 📈 **Automatic Visualizations**: Creates charts and graphs using matplotlib
- 🎨 **Modern UI**: Beautiful, responsive React frontend
- 🔒 **Secure**: Code runs in isolated E2B sandboxes

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 16+
- E2B API Key ([Get one here](https://e2b.dev/))
- Groq API Key ([Get one here](https://console.groq.com/))

### Installation

1. **Clone and setup Python environment**

```bash
# Install Python 3.10 (macOS)
brew install python@3.10

# Create virtual environment
python3 -m venv .hackathon_env_e2b

# Activate virtual environment
source .hackathon_env_e2b/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

2. **Setup environment variables**

Create a `.env` file in the root directory:

```bash
E2B_API_KEY=your_e2b_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

3. **Install frontend dependencies**

```bash
cd frontend
npm install
cd ..
```

### Running the Application

**Option 1: Use the startup scripts**

```bash
# Terminal 1: Start backend
chmod +x start_backend.sh
./start_backend.sh

# Terminal 2: Start frontend
chmod +x start_frontend.sh
./start_frontend.sh
```

**Option 2: Manual startup**

```bash
# Terminal 1: Start Flask backend
source .hackathon_env_e2b/bin/activate
cd backend
python app.py

# Terminal 2: Start React frontend
cd frontend
npm start
```

The application will open automatically at `http://localhost:3000`

## 📖 How to Use

1. **Upload CSV**: Drag and drop your CSV file or click to browse
2. **Wait for Processing**: The system will analyze your CSV structure
3. **Ask Questions**: Type natural language questions like:
   - "Show me the distribution of the first column"
   - "What are the summary statistics?"
   - "Create a correlation heatmap"
   - "Show trends over time"
4. **View Results**: Get AI-generated explanations and visualizations

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   React     │ HTTP │   Flask     │ API  │    Groq     │
│  Frontend   │─────▶│   Backend   │─────▶│  (Llama 3)  │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            │ Code
                            ▼
                     ┌─────────────┐
                     │     E2B     │
                     │   Sandbox   │
                     └─────────────┘
```

## 📁 Project Structure

```
e2b_hackathon/
├── backend/
│   └── app.py              # Flask API server
├── frontend/
│   ├── public/
│   │   └── index.html      # HTML template
│   └── src/
│       ├── App.js          # Main React component
│       ├── App.css         # Styles
│       ├── index.js        # React entry point
│       └── index.css       # Global styles
├── uploads/                # Uploaded CSV files
├── charts/                 # Generated visualizations
├── requirements.txt        # Python dependencies
├── start_backend.sh        # Backend startup script
├── start_frontend.sh       # Frontend startup script
└── README.md              # This file
```

## 🛠️ Technologies

- **Frontend**: React, Axios
- **Backend**: Flask, Flask-CORS
- **AI**: Groq (Llama 3.3 70B)
- **Code Execution**: E2B Code Interpreter
- **Data Analysis**: Pandas, Matplotlib, NumPy

## 🔧 API Endpoints

- `POST /api/upload` - Upload CSV file
- `POST /api/chat` - Send analysis query
- `GET /api/chart/<filename>` - Retrieve generated charts
- `POST /api/session/close` - Close sandbox session
- `GET /api/health` - Health check

## 💡 Example Queries

- "Show me the first 10 rows"
- "What's the average of column X?"
- "Create a bar chart of top 10 values"
- "Show correlation between columns A and B"
- "Find outliers in the dataset"
- "Group by category and show counts"

## 🐛 Troubleshooting

**Backend won't start:**
- Ensure `.env` file exists with valid API keys
- Check Python virtual environment is activated
- Verify all dependencies are installed

**Frontend won't start:**
- Delete `node_modules` and run `npm install` again
- Check Node.js version (16+ required)

**Code execution errors:**
- Verify E2B API key is valid
- Check internet connection
- Ensure CSV is properly formatted

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

---

Made with ❤️ using Groq AI and E2B

