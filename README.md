
# 🤖 CSV Analyzer AI Assistant

An intelligent AI assistant that analyzes CSV files using **Gemini AI** for natural language understanding and **E2B** for secure Python code execution in sandboxed environments.

## ✨ Features

- 📊 **CSV Upload & Analysis**: Drag-and-drop CSV files for instant analysis
- 💬 **Natural Language Queries**: Ask questions in plain English about your data
- 🐍 **Python Code Execution**: AI generates and executes Python code in E2B sandbox
- 📈 **Automatic Visualizations**: Creates charts and graphs using matplotlib
- 🔍 **Deep Web Research**: Use E2B MCP sandbox with Exa for comprehensive web research
- 🏢 **Competitor Analysis**: Upload company data, discover competitors, and generate competitive comparisons
- 🌐 **Web Scraping**: Scrape competitor websites using Browserbase MCP in E2B sandboxes
- 📋 **Comparison Tables**: Side-by-side feature and pricing comparisons with AI insights
- 🎨 **Modern UI**: Beautiful, responsive React frontend
- 🔒 **Secure**: Code runs in isolated E2B sandboxes

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 16+
- E2B API Key ([Get one here](https://e2b.dev/))
- Groq API Key ([Get one here](https://console.groq.com/))
- Exa API Key ([Get one here](https://exa.ai/)) - For web research and competitor discovery
- Browserbase API Key ([Get one here](https://browserbase.com/)) - For competitor website scraping

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
EXA_API_KEY=your_exa_api_key_here  # For web research and competitor discovery
BROWSERBASE_API_KEY=your_browserbase_api_key_here  # For competitor website scraping
BROWSERBASE_PROJECT_ID=your_browserbase_project_id_here
```

**Note**: 
- `EXA_API_KEY` is required for competitor discovery and web research features
- `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID` are required for competitor website scraping
- See `.env.example` for a complete template

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

### Data Analysis
- `POST /api/upload` - Upload CSV/JSON file (supports company data schema)
- `POST /api/chat` - Send analysis query (supports competitor analysis queries)
- `GET /api/chart/<filename>` - Retrieve generated charts
- `POST /api/session/close` - Close sandbox session

### Web Research
- `POST /api/research` - Perform web research using Exa MCP

### Competitor Analysis
- `POST /api/competitor/discover` - Discover competitors using Exa
- `POST /api/competitor/scrape` - Scrape competitor website using Browserbase MCP
- `POST /api/competitor/compare` - Generate competitive comparison table

### System
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

## 🔍 Web Research Feature

The application supports deep web research using E2B MCP (Model Context Protocol) sandboxes with Exa for web search.

### Setup

1. Get an Exa API key from [Exa AI](https://exa.ai/)
2. Add it to your `.env` file:
   ```bash
   EXA_API_KEY=your_exa_api_key_here
   ```

### Usage

Send a POST request to `/api/research`:

```bash
curl -X POST http://localhost:5000/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What happened last week in AI?",
    "session_id": "my_research_session"
  }'
```

The research endpoint:
- Creates an E2B sandbox with Exa MCP server enabled
- Uses Groq AI with MCP tools
- Performs comprehensive web searches using Exa
- Returns detailed research results with sources

### Example Research Queries

- "What are the latest developments in quantum computing?"
- "Find recent research papers about large language models"
- "What happened in the tech industry this month?"

## 🏢 Competitor Analysis Feature

Analyze your company against competitors with automated discovery, web scraping, and AI-powered insights.

### Company Data Schema

Upload a CSV or JSON file with your company information:

```json
{
  "company_name": "Your Company",
  "industry": "SaaS",
  "description": "Brief description of what you do",
  "website": "https://yourcompany.com",
  "features": [
    {"name": "Feature 1", "description": "Description", "category": "Core"},
    {"name": "Feature 2", "description": "Description", "category": "Premium"}
  ],
  "pricing": {
    "tiers": [
      {
        "name": "Starter",
        "price": "$49",
        "billing_period": "monthly",
        "features": ["Feature 1", "Feature 2"]
      }
    ]
  }
}
```

### Workflow

1. **Upload Company Data**
   ```bash
   curl -X POST http://localhost:5000/api/upload \
     -F "file=@company_data.json" \
     -F "session_id=my_session"
   ```

2. **Discover Competitors**
   ```bash
   curl -X POST http://localhost:5000/api/competitor/discover \
     -H "Content-Type: application/json" \
     -d '{"session_id": "my_session"}'
   ```

3. **Scrape Competitor Website**
   ```bash
   curl -X POST http://localhost:5000/api/competitor/scrape \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "my_session",
       "url": "https://competitor.com"
     }'
   ```

4. **Generate Comparison**
   ```bash
   curl -X POST http://localhost:5000/api/competitor/compare \
     -H "Content-Type: application/json" \
     -d '{"session_id": "my_session"}'
   ```

### Natural Language Queries

You can also use the chat interface with natural language:

- **"Find competitors"** - Automatically discovers competitors in your industry
- **"Compare with competitors"** - Generates a comprehensive comparison table
- **"What are my competitive advantages?"** - Shows features unique to your company
- **"What features am I missing?"** - Identifies gaps compared to competitors

### How It Works

1. **Company Data Validation**: Validates uploaded data against company schema
2. **Competitor Discovery**: Uses Exa MCP to find competitors based on industry and company description
3. **Web Scraping**: Uses Browserbase MCP in E2B sandboxes to scrape competitor websites
4. **Data Extraction**: Uses Groq AI to extract structured pricing and features from HTML
5. **Comparison Generation**: Creates side-by-side comparisons with AI-powered insights

### Features

- ✅ **Automated Discovery**: Find competitors automatically using Exa
- 🌐 **Secure Scraping**: All scraping happens in isolated E2B sandboxes
- 🤖 **AI Extraction**: Groq AI extracts structured data from unstructured HTML
- 📊 **Smart Comparisons**: Identifies advantages, gaps, and strategic opportunities
- 💡 **Strategic Insights**: AI-generated recommendations based on competitive landscape

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

---

Made with ❤️ using Groq AI and E2B

# e2b_hackathon
# Team_Members : 
Shaheriyar Zahed
Vignesh Gunda
Jaidev Shah

