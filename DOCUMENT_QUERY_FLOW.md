# Document Query Flow Diagram

## What Happens When You Ask a Question About Google Drive Uploaded Documents

```mermaid
flowchart TD
    Start([User Asks Question<br/>e.g., 'What does the document say about X?']] --> CheckType{Query Type<br/>Determination}
    
    CheckType -->|LLM Analysis| LLM[Qwen3/Groq<br/>Analyzes Query Intent]
    LLM -->|Explicitly mentions<br/>documents/files| DocSearch[Query Type:<br/>document_search]
    LLM -->|General question| WebSearch[Query Type:<br/>web_search_only]
    LLM -->|CSV analysis| CSVSearch[Query Type:<br/>csv_only]
    
    DocSearch --> CheckDocs{Documents<br/>Available?}
    CheckDocs -->|No| Fallback[Fallback to<br/>web_search_only]
    CheckDocs -->|Yes| GetSandbox[Get/Create E2B Sandbox<br/>for Session]
    
    GetSandbox --> AgenticSearch[Step 1: Agentic Search<br/>semtools search<br/>RUNNING IN E2B SANDBOX]
    
    AgenticSearch --> ScanFiles[Scan Documents Directory<br/>/home/user/documents<br/>INSIDE SANDBOX]
    ScanFiles --> FindFiles[Find All Files:<br/>PDFs, DOCX, TXT, MD<br/>INSIDE SANDBOX]
    
    FindFiles --> CheckParsed{Already<br/>Parsed Files?}
    CheckParsed -->|Yes| SearchParsed[semtools search<br/>on parsed text files<br/>RUNNING IN SANDBOX]
    CheckParsed -->|No| SearchAll[Search All Documents<br/>using file metadata<br/>INSIDE SANDBOX]
    
    SearchParsed --> ExtractRelevant[Extract Relevant Files<br/>Based on Query Similarity<br/>Results from Sandbox]
    SearchAll --> ExtractRelevant
    
    ExtractRelevant --> IdentifyPDFs[Identify PDFs<br/>That Need Parsing<br/>INSIDE SANDBOX]
    
    IdentifyPDFs --> CheckLlamaParse{LlamaParse<br/>Available?}
    
    CheckLlamaParse -->|Yes<br/>LLAMA_CLOUD_API_KEY set| LlamaParse[Step 2: LlamaParse Extraction<br/>semtools parse with LlamaParse<br/>RUNNING IN E2B SANDBOX]
    CheckLlamaParse -->|No| FallbackParse[Step 2: Fallback Parsing<br/>PyPDF2 or pdfplumber<br/>RUNNING IN E2B SANDBOX]
    
    LlamaParse --> ParsePDF1[Parse PDF 1<br/>Extract Text to Markdown<br/>INSIDE SANDBOX]
    LlamaParse --> ParsePDF2[Parse PDF 2<br/>Extract Text to Markdown<br/>INSIDE SANDBOX]
    LlamaParse --> ParsePDFN[Parse PDF N<br/>Max 5 PDFs<br/>INSIDE SANDBOX]
    
    FallbackParse --> ParsePDF1
    
    ParsePDF1 --> CombineResults[Step 3: Combine Results]
    ParsePDF2 --> CombineResults
    ParsePDFN --> CombineResults
    ExtractRelevant --> CombineResults
    
    CombineResults --> MergeContent[Merge:<br/>- Search Results Preview<br/>- Extracted PDF Content<br/>- Relevant Text Snippets]
    
    MergeContent --> GenerateAnswer[Step 4: Generate Answer<br/>Qwen3/Groq]
    
    GenerateAnswer --> CreatePrompt[Create Answer Prompt:<br/>User Question +<br/>Search Results +<br/>PDF Content]
    
    CreatePrompt --> CallGroq[Call Groq API<br/>Model: qwen/qwen3-32b<br/>Temperature: 0.3<br/>Max Tokens: 1024]
    
    CallGroq --> FinalAnswer[Final Answer<br/>Returned to User]
    
    Fallback --> WebSearchFlow[Web Research Flow<br/>Using Exa API]
    WebSearchFlow --> FinalAnswer
    
    CSVSearch --> CSVFlow[CSV Analysis Flow<br/>Generate Python Code]
    CSVFlow --> FinalAnswer
    
    style Start fill:#e1f5ff
    style GetSandbox fill:#e3f2fd
    style AgenticSearch fill:#fff4e1
    style LlamaParse fill:#e8f5e9
    style FallbackParse fill:#fff9c4
    style GenerateAnswer fill:#f3e5f5
    style FinalAnswer fill:#c8e6c9
```

## Detailed Step-by-Step Process

### Phase 1: Query Classification
1. **User asks question** → Frontend sends to `/api/chat`
2. **LLM Analysis** → Qwen3/Groq determines query type
   - Checks if query explicitly mentions "document", "file", "uploaded", etc.
   - If yes → `document_search`
   - If no → `web_search_only` or `csv_only`

### Phase 2: Agentic Search (if document_search) - **ALL IN E2B SANDBOX**
3. **Get E2B Sandbox** → Creates or retrieves sandbox instance for the session
   - Each session has its own isolated sandbox
   - Sandbox runs in secure, isolated environment

4. **Scan Documents** → **INSIDE SANDBOX**: System scans `/home/user/documents/` directory
   - Finds: PDFs, DOCX, TXT, MD files
   - Checks for already parsed text files
   - All file operations happen inside the sandbox

5. **Semantic Search** → **INSIDE SANDBOX**: Uses `semtools search` command
   - Executes via `sandbox.run_code()` to run Python code in sandbox
   - Python code runs `subprocess.run()` to execute `semtools search` command
   - Searches parsed text files first (if available)
   - Uses embeddings to find semantically similar content
   - Returns top-k relevant files (default: top 5)
   - Includes context lines around matches
   - All search happens inside the E2B sandbox

6. **Identify PDFs** → **INSIDE SANDBOX**: From relevant files, identifies PDFs that need parsing

### Phase 3: PDF Text Extraction - **ALL IN E2B SANDBOX**
7. **Check LlamaParse** → Checks if `LLAMA_CLOUD_API_KEY` is set

8a. **If LlamaParse Available (INSIDE SANDBOX):**
    - Uses `semtools parse` command with LlamaParse backend
    - Executes via `sandbox.run_code()` inside E2B sandbox
    - Sends PDF to LlamaParse API (external API call from sandbox)
    - Receives high-quality markdown/text extraction
    - Handles complex PDFs (tables, images, layouts)
    - Saves extracted text inside sandbox filesystem

8b. **If LlamaParse Not Available (INSIDE SANDBOX):**
    - Falls back to PyPDF2 or pdfplumber
    - Executes via `sandbox.run_code()` inside E2B sandbox
    - Basic text extraction
    - May miss complex layouts
    - Saves extracted text inside sandbox filesystem

9. **Extract Text** → **INSIDE SANDBOX**: For each relevant PDF (max 5):
    - Extracts text content
    - Saves as markdown or text file in `/home/user/documents/`
    - Limits to 2000 characters per PDF for response
    - Results read from sandbox stdout/logs back to backend

### Phase 4: Answer Generation
9. **Combine Results** → Merges:
   - Search results preview (from agentic search)
   - Extracted PDF content (from LlamaParse/fallback)
   - Relevant text snippets with context

10. **Generate Answer** → Creates prompt with:
    - User's original question
    - Combined search results
    - Extracted PDF content

11. **Call Groq** → Sends to Qwen3/Groq:
    - Model: `qwen/qwen3-32b`
    - Temperature: 0.3 (focused, factual)
    - Max tokens: 1024
    - System prompt: "Answer questions based on document content"

12. **Return Answer** → Final answer sent to frontend and displayed to user

## Key Components

### Tools Used:
- **semtools**: Agentic search and document parsing
- **LlamaParse**: High-quality PDF text extraction (optional)
- **PyPDF2/pdfplumber**: Fallback PDF parsing
- **Qwen3/Groq**: Query classification and answer generation

### E2B Sandbox (Execution Environment):
- **ALL document operations run inside isolated E2B sandbox**
- Agentic search (`semtools search`) executes via `sandbox.run_code()`
- PDF parsing (`semtools parse`, PyPDF2, pdfplumber) executes via `sandbox.run_code()`
- Documents stored in `/home/user/documents/` **inside the sandbox**
- Parsed files cached in sandbox filesystem for future searches
- Each session has its own sandbox instance
- Sandbox provides secure, isolated execution environment
- Results are read from sandbox stdout/logs back to backend

### Optimization:
- Only parses PDFs that are relevant to the query
- Limits to 5 PDFs per query
- Caches parsed text files
- Uses semantic search to narrow down documents first

## Example Flow

**User Input:**
```
"What does the document say about revenue projections?"
```

**Process:**
1. LLM classifies as `document_search`
2. **E2B Sandbox**: Agentic search (semtools) finds `revenue_report.pdf` as relevant
   - Search executes inside sandbox via `sandbox.run_code()`
3. **E2B Sandbox**: LlamaParse extracts text from `revenue_report.pdf`
   - Parsing executes inside sandbox via `sandbox.run_code()`
   - Text saved in sandbox filesystem
4. Backend reads results from sandbox and combines: search results + extracted PDF text
5. Qwen3 generates answer based on the content (runs on backend, not in sandbox)
6. User receives answer with specific information from the PDF

