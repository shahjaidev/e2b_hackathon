"""Browserbase MCP client for web scraping in E2B sandboxes"""
import os
import time
import re
from typing import Dict, Optional
from e2b import Sandbox as E2BSandbox


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    # Basic URL pattern
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(url):
        return False, f"Invalid URL format: {url}"
    
    return True, ""


def create_browserbase_sandbox(session_id: str) -> E2BSandbox:
    """
    Create E2B MCP sandbox with Browserbase enabled
    
    Args:
        session_id: Session identifier
        
    Returns:
        E2B sandbox instance with Browserbase MCP
    """
    print(f"🌐 Creating E2B MCP sandbox with Browserbase for session: {session_id}")
    
    browserbase_api_key = os.getenv('BROWSERBASE_API_KEY')
    browserbase_project_id = os.getenv('BROWSERBASE_PROJECT_ID')
    exa_api_key = os.getenv('EXA_API_KEY')
    
    if not browserbase_api_key or not browserbase_project_id:
        raise ValueError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in environment variables")
    
    # Create E2B sandbox with both Exa and Browserbase MCP
    mcp_config = {
        "browserbase": {
            "apiKey": browserbase_api_key,
            "projectId": browserbase_project_id
        }
    }
    
    # Add Exa if available (for combined operations)
    if exa_api_key:
        mcp_config["exa"] = {"apiKey": exa_api_key}
    
    try:
        sandbox = E2BSandbox.create(mcp=mcp_config)
        print(f"✅ Browserbase MCP sandbox created successfully")
        return sandbox
    except Exception as e:
        print(f"❌ Failed to create Browserbase sandbox: {e}")
        raise


def scrape_url_in_sandbox(sandbox: E2BSandbox, url: str, max_retries: int = 3) -> Dict:
    """
    Scrape URL using Browserbase MCP within E2B sandbox
    
    Args:
        sandbox: E2B MCP sandbox
        url: URL to scrape
        max_retries: Maximum number of retry attempts
        
    Returns:
        {"html": str, "text": str, "url": str, "status": str}
    """
    print(f"🌐 Scraping URL in E2B sandbox: {url}")
    
    for attempt in range(max_retries):
        try:
            # Get MCP URL and token from sandbox
            mcp_url = sandbox.get_mcp_url() if hasattr(sandbox, 'get_mcp_url') else getattr(sandbox, 'mcp_url', None)
            mcp_token = sandbox.get_mcp_token() if hasattr(sandbox, 'get_mcp_token') else getattr(sandbox, 'mcp_token', None)
            
            if not mcp_url or not mcp_token:
                raise ValueError("Could not retrieve MCP configuration from sandbox")
            
            # Use OpenAI-compatible client to call Browserbase MCP
            from openai import OpenAI
            
            groq_openai_client = OpenAI(
                api_key=os.getenv('GROQ_API_KEY'),
                base_url='https://api.groq.com/openai/v1'
            )
            
            # Call Groq with MCP tools to scrape the URL
            scrape_prompt = f"""Scrape the content from this URL: {url}

Use the Browserbase tool to navigate to the URL and extract:
1. The full HTML content
2. The visible text content
3. Any errors encountered

Return the results in a structured format."""
            
            response = groq_openai_client.chat.completions.create(
                model="qwen/qwen3-32b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a web scraping assistant. Use Browserbase to scrape websites and return the content."
                    },
                    {
                        "role": "user",
                        "content": scrape_prompt
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
                temperature=0.1,
                max_tokens=4096
            )
            
            result_text = response.choices[0].message.content
            
            if not result_text or len(result_text.strip()) == 0:
                raise ValueError("Scraping returned empty result")
            
            print(f"✅ Successfully scraped {url} ({len(result_text)} chars)")
            
            return {
                "html": result_text,
                "text": result_text,
                "url": url,
                "status": "success",
                "method": "browserbase_mcp"
            }
            
        except Exception as e:
            print(f"❌ Scraping attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if attempt < max_retries - 1:
                # Exponential backoff
                wait_time = 2 ** attempt
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                # Final attempt failed - return error
                print(f"❌ All scraping attempts failed for {url}")
                return {
                    "html": "",
                    "text": "",
                    "url": url,
                    "status": "error",
                    "error": str(e),
                    "method": "browserbase_mcp"
                }
    
    return {
        "html": "",
        "text": "",
        "url": url,
        "status": "error",
        "error": "Max retries exceeded",
        "method": "browserbase_mcp"
    }


def find_pricing_page(sandbox: E2BSandbox, base_url: str) -> str:
    """
    Try to find the pricing page for a website
    
    Args:
        sandbox: E2B MCP sandbox
        base_url: Base URL of the website
        
    Returns:
        URL of pricing page (or base_url if not found)
    """
    print(f"🔍 Looking for pricing page at {base_url}")
    
    common_paths = [
        "/pricing",
        "/plans",
        "/buy",
        "/purchase",
        "/get-started",
        "/pricing-plans",
        "/price",
        "/cost"
    ]
    
    # Try common pricing page paths
    for path in common_paths:
        test_url = base_url.rstrip('/') + path
        
        try:
            # Quick check if URL exists (we'll do a lightweight request)
            import requests
            response = requests.head(test_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                print(f"✅ Found pricing page: {test_url}")
                return test_url
        except:
            continue
    
    print(f"⚠️  No pricing page found, using homepage: {base_url}")
    return base_url


def find_features_page(sandbox: E2BSandbox, base_url: str) -> str:
    """
    Try to find the features page for a website
    
    Args:
        sandbox: E2B MCP sandbox
        base_url: Base URL of the website
        
    Returns:
        URL of features page (or base_url if not found)
    """
    print(f"🔍 Looking for features page at {base_url}")
    
    common_paths = [
        "/features",
        "/product",
        "/capabilities",
        "/solutions",
        "/platform",
        "/what-we-do",
        "/products",
        "/services"
    ]
    
    # Try common features page paths
    for path in common_paths:
        test_url = base_url.rstrip('/') + path
        
        try:
            # Quick check if URL exists
            import requests
            response = requests.head(test_url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                print(f"✅ Found features page: {test_url}")
                return test_url
        except:
            continue
    
    print(f"⚠️  No features page found, using homepage: {base_url}")
    return base_url


def scrape_competitor_pages(sandbox: E2BSandbox, base_url: str) -> Dict:
    """
    Scrape homepage, pricing, and features pages for a competitor
    
    Args:
        sandbox: E2B MCP sandbox
        base_url: Base URL of competitor website
        
    Returns:
        Dictionary with scraped content from all pages
    """
    print(f"\n{'='*60}")
    print(f"🌐 Scraping competitor: {base_url}")
    print(f"{'='*60}\n")
    
    results = {
        "base_url": base_url,
        "homepage": {},
        "pricing": {},
        "features": {},
        "status": "in_progress"
    }
    
    # 1. Scrape homepage
    print("1️⃣ Scraping homepage...")
    results["homepage"] = scrape_url_in_sandbox(sandbox, base_url)
    
    # 2. Find and scrape pricing page
    print("\n2️⃣ Finding pricing page...")
    pricing_url = find_pricing_page(sandbox, base_url)
    if pricing_url != base_url:
        print("3️⃣ Scraping pricing page...")
        results["pricing"] = scrape_url_in_sandbox(sandbox, pricing_url)
    else:
        print("⚠️  Using homepage for pricing info")
        results["pricing"] = results["homepage"]
    
    # 3. Find and scrape features page
    print("\n4️⃣ Finding features page...")
    features_url = find_features_page(sandbox, base_url)
    if features_url != base_url:
        print("5️⃣ Scraping features page...")
        results["features"] = scrape_url_in_sandbox(sandbox, features_url)
    else:
        print("⚠️  Using homepage for features info")
        results["features"] = results["homepage"]
    
    # Check overall status
    all_success = all(
        page.get("status") == "success" 
        for page in [results["homepage"], results["pricing"], results["features"]]
    )
    
    results["status"] = "success" if all_success else "partial"
    
    print(f"\n✅ Scraping complete for {base_url}")
    print(f"   Status: {results['status']}")
    
    return results
