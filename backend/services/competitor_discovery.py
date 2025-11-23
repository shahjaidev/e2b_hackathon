"""Competitor discovery service using Exa MCP"""
import os
from typing import List, Dict
from e2b import Sandbox as E2BSandbox
from openai import OpenAI


def discover_competitors(
    company_name: str,
    industry: str,
    description: str = "",
    num_results: int = 5,
    research_sandbox: E2BSandbox = None
) -> List[Dict]:
    """
    Discover competitors using Exa MCP in E2B sandbox
    
    Args:
        company_name: User's company name
        industry: Industry/market
        description: Company description (optional)
        num_results: Number of competitors to find
        research_sandbox: Existing E2B MCP sandbox (optional)
        
    Returns:
        List of {"name": str, "url": str, "description": str}
    """
    print(f"\n🔍 Discovering competitors for {company_name} in {industry}...")
    
    # Construct search query
    search_query = construct_exa_query(company_name, industry, description)
    print(f"   Search query: {search_query}")
    
    # Create or use existing sandbox
    close_sandbox = False
    if research_sandbox is None:
        print("   Creating new E2B MCP sandbox with Exa...")
        exa_api_key = os.getenv('EXA_API_KEY')
        if not exa_api_key:
            print("❌ EXA_API_KEY not configured")
            return []
        
        try:
            research_sandbox = E2BSandbox.create(
                mcp={"exa": {"apiKey": exa_api_key}}
            )
            close_sandbox = True
        except Exception as e:
            print(f"❌ Failed to create Exa sandbox: {e}")
            return []
    
    try:
        # Get MCP configuration
        mcp_url = research_sandbox.get_mcp_url() if hasattr(research_sandbox, 'get_mcp_url') else getattr(research_sandbox, 'mcp_url', None)
        mcp_token = research_sandbox.get_mcp_token() if hasattr(research_sandbox, 'get_mcp_token') else getattr(research_sandbox, 'mcp_token', None)
        
        if not mcp_url or not mcp_token:
            raise ValueError("Could not retrieve MCP configuration")
        
        # Use Groq with Exa MCP to search
        groq_openai_client = OpenAI(
            api_key=os.getenv('GROQ_API_KEY'),
            base_url='https://api.groq.com/openai/v1'
        )
        
        research_prompt = f"""Find competitor companies for: {company_name}

Industry: {industry}
Description: {description}

Use Exa to search for {num_results} competitor companies in the same industry. 
For each competitor, provide:
1. Company name
2. Website URL
3. Brief description (1-2 sentences)

Focus on direct competitors that offer similar products/services.
Return results in a clear, structured format."""
        
        print("   Calling Groq with Exa MCP...")
        response = groq_openai_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a competitive intelligence researcher. Use Exa to find competitor companies and return structured information."
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
            temperature=0.3,
            max_tokens=2048
        )
        
        result_text = response.choices[0].message.content
        
        if not result_text or len(result_text.strip()) == 0:
            print("⚠️  Exa search returned empty result")
            return []
        
        # Parse the result to extract competitors
        competitors = parse_competitor_results(result_text, company_name)
        
        print(f"✅ Found {len(competitors)} competitors")
        for i, comp in enumerate(competitors, 1):
            print(f"   {i}. {comp['name']} - {comp['url']}")
        
        return competitors
        
    except Exception as e:
        print(f"❌ Error discovering competitors: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if close_sandbox and research_sandbox:
            try:
                research_sandbox.kill()
            except:
                pass


def construct_exa_query(company_name: str, industry: str, description: str) -> str:
    """
    Construct Exa search query from company information
    
    Args:
        company_name: Company name
        industry: Industry/market
        description: Company description
        
    Returns:
        Search query string
    """
    # Build query with industry and key terms
    query_parts = []
    
    # Add industry
    if industry:
        query_parts.append(industry)
    
    # Add "competitors" or "alternatives"
    query_parts.append("competitors")
    query_parts.append("alternatives")
    
    # Add company name for context (but we'll filter it out later)
    if company_name:
        query_parts.append(f"similar to {company_name}")
    
    # Add key terms from description
    if description:
        # Extract key terms (simple approach)
        key_terms = [word for word in description.split() if len(word) > 5][:3]
        query_parts.extend(key_terms)
    
    return " ".join(query_parts)


def parse_competitor_results(result_text: str, exclude_company: str) -> List[Dict]:
    """
    Parse competitor information from Exa/Groq response
    
    Args:
        result_text: Response text from Groq/Exa
        exclude_company: Company name to exclude (user's own company)
        
    Returns:
        List of competitor dictionaries
    """
    competitors = []
    
    # Extract URLs using regex
    import re
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    urls = re.findall(url_pattern, result_text)
    
    # Clean URLs and deduplicate
    seen_domains = set()
    for url in urls:
        # Clean URL
        url = url.rstrip('.,;:)')
        
        # Extract domain
        domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            
            # Skip if already seen or if it's the user's company
            if domain in seen_domains:
                continue
            if exclude_company and exclude_company.lower() in domain.lower():
                continue
            
            seen_domains.add(domain)
            
            # Ensure URL has protocol
            if not url.startswith('http'):
                url = 'https://' + url
            
            # Extract company name from domain
            company_name = domain.split('.')[0].title()
            
            # Try to find description in text near the URL
            description = extract_description_near_url(result_text, url)
            
            competitors.append({
                "name": company_name,
                "url": url,
                "description": description
            })
    
    return competitors


def extract_description_near_url(text: str, url: str) -> str:
    """
    Extract description text near a URL
    
    Args:
        text: Full text
        url: URL to find
        
    Returns:
        Description string
    """
    # Find the URL position
    url_pos = text.find(url)
    if url_pos == -1:
        return ""
    
    # Get text around the URL (100 chars before and after)
    start = max(0, url_pos - 100)
    end = min(len(text), url_pos + len(url) + 100)
    context = text[start:end]
    
    # Extract sentences
    import re
    sentences = re.split(r'[.!?\n]', context)
    
    # Find the sentence with the URL
    for sentence in sentences:
        if url in sentence or len(sentence) > 20:
            return sentence.strip()
    
    return ""
