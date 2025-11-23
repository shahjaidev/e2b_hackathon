"""Groq-based data extraction from HTML"""
import os
import json
from typing import Dict, List
from groq import Groq


# Initialize Groq client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
MODEL = "qwen/qwen3-32b"  # Fast and efficient model


# Extraction prompts
PRICING_EXTRACTION_PROMPT = """You are analyzing a pricing page. Extract all pricing tiers and their details.

URL: {url}

HTML Content (first 6000 chars):
{html}

Extract pricing information and return ONLY valid JSON in this exact format:
{{
  "tiers": [
    {{
      "name": "Starter",
      "price": "$49",
      "billing_period": "monthly",
      "features": ["Feature 1", "Feature 2"]
    }}
  ]
}}

IMPORTANT:
- Extract ALL pricing tiers you find
- Include the currency symbol in price (e.g., "$49", "€99", "Free")
- billing_period should be: "monthly", "yearly", "annual", "one-time", or "custom"
- List key features included in each tier
- If no pricing found, return: {{"tiers": []}}

Return ONLY the JSON, no explanations."""

FEATURES_EXTRACTION_PROMPT = """You are analyzing a product features page. Extract all product features mentioned.

URL: {url}

HTML Content (first 6000 chars):
{html}

Extract features and return ONLY valid JSON in this exact format:
{{
  "features": [
    {{
      "name": "Feature Name",
      "description": "Brief description if available",
      "category": "Category if mentioned"
    }}
  ]
}}

IMPORTANT:
- Extract ALL features mentioned on the page
- Include description if available (can be empty string if not)
- Include category if mentioned (can be empty string if not)
- If no features found, return: {{"features": []}}

Return ONLY the JSON, no explanations."""

COMPANY_INFO_EXTRACTION_PROMPT = """You are analyzing a company website. Extract basic company information.

URL: {url}

HTML Content (first 6000 chars):
{html}

Extract company information and return ONLY valid JSON in this exact format:
{{
  "company_name": "Company Name",
  "description": "Brief description of what the company does",
  "industry": "Industry or category"
}}

IMPORTANT:
- Extract the company name from the page
- Write a brief 1-2 sentence description
- Identify the industry/category
- If information not found, use empty strings

Return ONLY the JSON, no explanations."""


def extract_pricing_from_html(html: str, url: str) -> Dict:
    """
    Extract pricing information from HTML using Groq
    
    Args:
        html: HTML content
        url: Source URL
        
    Returns:
        Pricing data matching company schema
    """
    print(f"💰 Extracting pricing from {url}...")
    
    try:
        # Truncate HTML to avoid token limits
        html_truncated = html[:6000]
        
        prompt = PRICING_EXTRACTION_PROMPT.format(url=url, html=html_truncated)
        
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction expert. Extract structured data from HTML and return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2048
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1])  # Remove first and last lines
            if result.startswith("json"):
                result = result[4:].strip()
        
        # Parse JSON
        pricing_data = json.loads(result)
        
        # Validate structure
        if "tiers" not in pricing_data:
            pricing_data = {"tiers": []}
        
        print(f"✅ Extracted {len(pricing_data['tiers'])} pricing tiers")
        return pricing_data
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"   Response was: {result[:200]}")
        return {"tiers": []}
    except Exception as e:
        print(f"❌ Error extracting pricing: {e}")
        return {"tiers": []}


def extract_features_from_html(html: str, url: str) -> List[Dict]:
    """
    Extract features from HTML using Groq
    
    Args:
        html: HTML content
        url: Source URL
        
    Returns:
        Features list matching company schema
    """
    print(f"✨ Extracting features from {url}...")
    
    try:
        # Truncate HTML to avoid token limits
        html_truncated = html[:6000]
        
        prompt = FEATURES_EXTRACTION_PROMPT.format(url=url, html=html_truncated)
        
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction expert. Extract structured data from HTML and return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2048
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1])
            if result.startswith("json"):
                result = result[4:].strip()
        
        # Parse JSON
        features_data = json.loads(result)
        
        # Validate structure
        if "features" not in features_data:
            features_data = {"features": []}
        
        # Ensure each feature has required fields
        features = []
        for feature in features_data.get("features", []):
            if isinstance(feature, str):
                # Convert string to structured format
                features.append({
                    "name": feature,
                    "description": "",
                    "category": ""
                })
            elif isinstance(feature, dict):
                # Ensure all fields exist
                features.append({
                    "name": feature.get("name", ""),
                    "description": feature.get("description", ""),
                    "category": feature.get("category", "")
                })
        
        print(f"✅ Extracted {len(features)} features")
        return features
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"   Response was: {result[:200]}")
        return []
    except Exception as e:
        print(f"❌ Error extracting features: {e}")
        return []


def extract_company_info(html: str, url: str) -> Dict:
    """
    Extract basic company info from HTML
    
    Args:
        html: HTML content
        url: Source URL
        
    Returns:
        Company info dictionary
    """
    print(f"🏢 Extracting company info from {url}...")
    
    try:
        # Truncate HTML to avoid token limits
        html_truncated = html[:6000]
        
        prompt = COMPANY_INFO_EXTRACTION_PROMPT.format(url=url, html=html_truncated)
        
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a data extraction expert. Extract structured data from HTML and return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=512
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1])
            if result.startswith("json"):
                result = result[4:].strip()
        
        # Parse JSON
        company_info = json.loads(result)
        
        # Ensure all fields exist
        company_info = {
            "company_name": company_info.get("company_name", ""),
            "description": company_info.get("description", ""),
            "industry": company_info.get("industry", "")
        }
        
        print(f"✅ Extracted company info: {company_info.get('company_name', 'Unknown')}")
        return company_info
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return {"company_name": "", "description": "", "industry": ""}
    except Exception as e:
        print(f"❌ Error extracting company info: {e}")
        return {"company_name": "", "description": "", "industry": ""}


def extract_all_competitor_data(scraped_pages: Dict, base_url: str) -> Dict:
    """
    Extract all data from scraped competitor pages
    
    Args:
        scraped_pages: Dictionary with homepage, pricing, features HTML
        base_url: Base URL of competitor
        
    Returns:
        Complete competitor data matching company schema
    """
    print(f"\n{'='*60}")
    print(f"📊 Extracting data from competitor: {base_url}")
    print(f"{'='*60}\n")
    
    # Extract company info from homepage
    homepage_html = scraped_pages.get("homepage", {}).get("html", "")
    company_info = extract_company_info(homepage_html, base_url)
    
    # Extract pricing from pricing page
    pricing_html = scraped_pages.get("pricing", {}).get("html", "")
    pricing_data = extract_pricing_from_html(pricing_html, base_url)
    
    # Extract features from features page
    features_html = scraped_pages.get("features", {}).get("html", "")
    features_data = extract_features_from_html(features_html, base_url)
    
    # Combine into company data format
    competitor_data = {
        "company_name": company_info.get("company_name", ""),
        "industry": company_info.get("industry", ""),
        "description": company_info.get("description", ""),
        "website": base_url,
        "features": features_data,
        "pricing": pricing_data,
        "metrics": {},
        "url": base_url,
        "scraped_at": scraped_pages.get("timestamp", ""),
        "scraping_status": scraped_pages.get("status", "unknown")
    }
    
    print(f"\n✅ Data extraction complete for {base_url}")
    print(f"   Company: {competitor_data['company_name']}")
    print(f"   Features: {len(competitor_data['features'])}")
    print(f"   Pricing tiers: {len(competitor_data['pricing'].get('tiers', []))}")
    
    return competitor_data
