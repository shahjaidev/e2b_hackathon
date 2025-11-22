#!/bin/bash

echo "================================================"
echo "  CSV Analyzer AI Assistant - Setup Script"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python 3.10+ is installed
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2)
echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

# Check if Node.js is installed
echo "Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed. Please install Node.js 16+${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node.js $NODE_VERSION found${NC}"

# Create virtual environment
echo ""
echo "Setting up Python virtual environment..."
if [ ! -d ".hackathon_env_e2b" ]; then
    python3 -m venv .hackathon_env_e2b
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source .hackathon_env_e2b/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Install Node.js dependencies
echo ""
echo "Installing Node.js dependencies..."
cd frontend
npm install
cd ..
echo -e "${GREEN}✓ Node.js dependencies installed${NC}"

# Create necessary directories
echo ""
echo "Creating necessary directories..."
mkdir -p uploads
mkdir -p charts
mkdir -p backend
echo -e "${GREEN}✓ Directories created${NC}"

# Check for .env file
echo ""
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file not found${NC}"
    echo "Creating .env file from template..."
    cat > .env << EOF
# E2B API Key - Get from https://e2b.dev/
E2B_API_KEY=your_e2b_api_key_here

# Groq API Key - Get from https://console.groq.com/
GROQ_API_KEY=your_groq_api_key_here
EOF
    echo -e "${YELLOW}✓ .env file created${NC}"
    echo -e "${RED}IMPORTANT: Please edit .env and add your API keys!${NC}"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Make startup scripts executable
chmod +x start_backend.sh
chmod +x start_frontend.sh
echo -e "${GREEN}✓ Startup scripts are executable${NC}"

echo ""
echo "================================================"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys:"
echo "   - E2B_API_KEY: Get from https://e2b.dev/"
echo "   - GROQ_API_KEY: Get from https://console.groq.com/"
echo ""
echo "2. Start the application:"
echo "   Terminal 1: ./start_backend.sh"
echo "   Terminal 2: ./start_frontend.sh"
echo ""
echo "3. Open http://localhost:3000 in your browser"
echo ""
echo "================================================"

