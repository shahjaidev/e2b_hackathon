# Desk Research Agent Frontend

A Next.js frontend for a professional desk research platform designed for consulting firms like EY, McKinsey, Deloitte, and BCG.

## Overview

This frontend application provides the user interface for a desk research agent that can:

- Analyze CSV data files with AI-powered insights
- Perform comprehensive web research using Exa search
- Generate Python code for data analysis
- Create professional visualizations and charts
- Display code with syntax highlighting
- Export research findings for client presentations

## Features

- 🎯 Clean, professional chat interface
- 📊 CSV file upload and analysis
- 🔍 Web research capabilities
- 💻 Code generation and preview
- 📈 Automatic chart generation
- 🌳 File tree visualization
- 💾 Local storage for conversation history
- 💼 Consulting-ready outputs

## Tech Stack

- [Next.js 15](https://nextjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [shadcn/ui](https://ui.shadcn.com/)
- REST API for backend communication

## Prerequisites

Before running this frontend, ensure you have:

- Node.js 18.0.0 or higher
- A running backend instance (Flask backend on port 5000)
- Environment variables configured

## Getting Started

1. Install dependencies:

```bash
cd ai_assistant
npm install --legacy-peer-deps
# or
yarn install
# or
pnpm install
```

**Note**: Use `--legacy-peer-deps` flag with npm due to React 19 compatibility with some dependencies.

2. Configure environment variables:

Create a `.env.local` file:

```
NEXT_PUBLIC_API_URL=http://localhost:5000
```

3. Start the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
```

4. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Backend Requirements

This frontend works with a Flask backend that provides:

- `/api/upload` - CSV file upload endpoint
- `/api/chat` - Chat endpoint for queries (handles CSV analysis, web research, or both)
- `/api/chart/<filename>` - Chart image serving endpoint
- `/api/research` - Web research endpoint

Make sure your backend is running on the port specified in `NEXT_PUBLIC_API_URL`.

## Usage

1. **Start a conversation**: Click "Start a new conversation" or select an existing one
2. **Upload CSV files**: Click "Upload CSV" to upload data files for analysis
3. **Ask questions**: Type your questions about the data or request web research
4. **View code**: Click on code previews to open the code sidebar
5. **View charts**: Charts are automatically displayed when generated
6. **Export results**: Use the generated insights and visualizations for your research reports

## Use Cases

Perfect for consulting firms conducting:
- Market research and competitive analysis
- Industry trend analysis
- Client data analysis and insights
- Due diligence research
- Strategic planning support

## Project Structure

```
ai_assistant/
├── app/
│   ├── demo/
│   │   └── page.tsx          # Main chat interface
│   ├── page.tsx              # Landing page
│   └── layout.tsx            # Root layout
├── components/
│   ├── chat.tsx              # Chat component
│   ├── code-sidebar.tsx      # Code viewer sidebar
│   └── ui/                   # shadcn/ui components
├── contexts/
│   └── code-context.tsx      # Code state management
└── lib/
    └── utils.ts              # Utility functions
```

## Development

The frontend uses:
- **Next.js 15** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **shadcn/ui** for UI components

## License

MIT
