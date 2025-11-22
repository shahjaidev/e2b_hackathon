# 🚀 Complete Setup Guide

This guide will walk you through setting up the CSV Analyzer AI Assistant from scratch.

## 📋 Prerequisites

Before starting, make sure you have:

1. **Python 3.10 or higher**
   ```bash
   python3 --version  # Should be 3.10+
   ```
   If not installed on macOS:
   ```bash
   brew install python@3.10
   ```

2. **Node.js 16 or higher**
   ```bash
   node --version  # Should be 16+
   ```
   If not installed:
   - Download from [nodejs.org](https://nodejs.org/)
   - Or use `brew install node` on macOS

3. **API Keys** (free to get):
   - **E2B API Key**: Sign up at [e2b.dev](https://e2b.dev/)
   - **Groq API Key**: Get from [Groq Console](https://console.groq.com/)

## 🔧 Automated Setup (Recommended)

Run the setup script that handles everything:

```bash
# Make the setup script executable
chmod +x setup.sh

# Run the setup
./setup.sh
```

This will:
- Check all prerequisites
- Create Python virtual environment
- Install all Python dependencies
- Install all Node.js dependencies
- Create necessary directories
- Create a template .env file

After running the setup script, **edit the `.env` file** and add your API keys:

```bash
nano .env  # or use any text editor
```

Update these lines:
```
E2B_API_KEY=your_actual_e2b_api_key
GEMINI_API_KEY=your_actual_gemini_api_key
```

## 🛠️ Manual Setup (Alternative)

If you prefer to set things up manually:

### Step 1: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .hackathon_env_e2b

# Activate it
source .hackathon_env_e2b/bin/activate
```

### Step 2: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Step 4: Create Environment File

Create a `.env` file in the root directory:

```bash
cat > .env << 'EOF'
E2B_API_KEY=your_e2b_api_key_here
GROQ_API_KEY=your_groq_api_key_here
EOF
```

Then edit it with your actual API keys.

### Step 5: Create Directories

```bash
mkdir -p uploads charts backend
```

### Step 6: Make Scripts Executable

```bash
chmod +x start_backend.sh start_frontend.sh
```

## 🚀 Running the Application

### Option 1: Using Startup Scripts (Recommended)

Open two terminal windows:

**Terminal 1 - Backend:**
```bash
./start_backend.sh
```

**Terminal 2 - Frontend:**
```bash
./start_frontend.sh
```

### Option 2: Manual Start

**Terminal 1 - Backend:**
```bash
source .hackathon_env_e2b/bin/activate
cd backend
python app.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

## 🌐 Access the Application

Once both servers are running:
1. Frontend: `http://localhost:3000` (opens automatically)
2. Backend API: `http://localhost:5000`

## 🎯 Quick Test

1. Open `http://localhost:3000`
2. Drag and drop the included `dataset.csv` file
3. Try asking: "Show me the top 10 movies by vote average"
4. Watch the AI generate code and create visualizations!

## 🐛 Troubleshooting

### Backend Issues

**"ModuleNotFoundError: No module named 'flask'"**
- Make sure virtual environment is activated
- Run: `pip install -r requirements.txt`

**"E2B API key not found"**
- Check `.env` file exists in root directory
- Verify E2B_API_KEY is set correctly

**"Port 5000 already in use"**
- Kill the process: `lsof -ti:5000 | xargs kill -9`
- Or change port in `backend/app.py`

### Frontend Issues

**"npm command not found"**
- Install Node.js from [nodejs.org](https://nodejs.org/)

**"Port 3000 already in use"**
- When prompted, press `Y` to run on different port
- Or kill the process: `lsof -ti:3000 | xargs kill -9`

**"Cannot find module 'react'"**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### API Key Issues

**Invalid E2B API Key:**
1. Go to [e2b.dev](https://e2b.dev/)
2. Sign in/up
3. Go to Dashboard → API Keys
4. Copy your key to `.env`

**Invalid Groq API Key:**
1. Go to [Groq Console](https://console.groq.com/)
2. Sign up/sign in
3. Navigate to API Keys section
4. Create a new API key
5. Copy to `.env`

## 📦 Dependencies

### Backend (Python)
- flask - Web framework
- flask-cors - CORS support
- python-dotenv - Environment variables
- e2b-code-interpreter - Code execution
- groq - Groq AI (Llama 3.3)
- pandas - Data analysis

### Frontend (React)
- react - UI framework
- axios - HTTP client
- react-scripts - Build tools

## 🔄 Updating

To update dependencies:

**Python:**
```bash
source .hackathon_env_e2b/bin/activate
pip install --upgrade -r requirements.txt
```

**Node.js:**
```bash
cd frontend
npm update
```

## 🧹 Cleanup

To remove all generated files:

```bash
# Remove uploaded files
rm -rf uploads/*

# Remove generated charts
rm -rf charts/*

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -r {} +

# Remove virtual environment (if needed)
rm -rf .hackathon_env_e2b

# Remove node modules (if needed)
rm -rf frontend/node_modules
```

## 💡 Tips

1. **Keep terminals open**: Both backend and frontend need to run simultaneously
2. **Check logs**: If something doesn't work, check terminal output for errors
3. **Restart servers**: If changes aren't reflecting, restart both servers
4. **Clear browser cache**: If UI looks broken, clear cache and reload

## 📚 Additional Resources

- [E2B Documentation](https://e2b.dev/docs)
- [Groq API Documentation](https://console.groq.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)

## 🆘 Still Having Issues?

1. Check if all prerequisites are installed correctly
2. Verify API keys are valid and have proper permissions
3. Ensure no firewall is blocking ports 3000 or 5000
4. Try running the automated setup script again
5. Check the GitHub issues page for common problems

---

Happy analyzing! 🎉

