# 🚀 Quick Start Guide

## Prerequisites

1. Make sure you have a `.env` file with your API keys:
   ```
   E2B_API_KEY=your_e2b_key
   ANTHROPIC_API_KEY=your_anthropic_key
   GROQ_API_KEY=your_groq_key
   ```

2. Python virtual environment should be set up (`.hackathon_env_e2b`)

3. Node.js and npm installed

## Starting the Application

### Option 1: Using Start Scripts (Recommended)

**Terminal 1 - Start Backend:**
```bash
./start_backend.sh
```
Backend will run on: http://localhost:5000

**Terminal 2 - Start Frontend:**
```bash
./start_frontend.sh
```
Frontend will run on: http://localhost:3000

### Option 2: Manual Start

**Terminal 1 - Start Backend:**
```bash
source .hackathon_env_e2b/bin/activate
cd backend
pip install -r ../requirements.txt
python app.py
```

**Terminal 2 - Start Frontend:**
```bash
cd frontend
npm install  # First time only
npm start
```

## Testing

1. Open your browser to: **http://localhost:3000**
2. Upload a CSV file
3. Ask questions about your data!

## Troubleshooting

- **Backend won't start**: Check that `.env` file exists and has all API keys
- **Frontend won't start**: Run `npm install` in the `frontend` directory
- **Port already in use**: Stop any processes using ports 3000 or 5000
