"""Company data schema validation and parsing"""
from typing import Dict, List, Tuple, Any, Optional


# Company data schema definition
COMPANY_SCHEMA = {
    "required": ["company_name", "industry"],
    "optional": ["description", "website", "features", "pricing", "metrics", "product_name", "target_market", "founded", "headquarters", "financials"],
    "features_schema": {
        "name": str,
        "description": str,
        "category": str
    },
    "pricing_schema": {
        "tiers": [
            {
                "name": str,
                "price": (str, int, float),  # Can be "$10", 10, or "Custom"
                "billing_period": str,
                "features": [str]
            }
        ]
    },
    "financials_schema": {
        "quarters": [
            {
                "quarter": str,  # e.g., "Q1 2024"
                "year": int,
                "revenue": float,
                "expenses": float,
                "profit": float,
                "growth_rate": float
            }
        ]
    }
}

# Financial data indicators - columns that suggest this is financial data
FINANCIAL_INDICATORS = [
    "revenue", "expenses", "profit", "loss", "income", "cost", "sales",
    "quarter", "q1", "q2", "q3", "q4", "fiscal", "earnings", "ebitda",
    "gross_profit", "net_income", "operating_income", "cash_flow"
]


def validate_company_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], List[str]]:
    """
    Validate company data against schema (including financial data)
    
    Args:
        data: Parsed data from CSV/JSON/Excel
        
    Returns:
        Tuple of (is_valid, structured_data, errors)
        - is_valid: True if data passes validation
        - structured_data: Normalized company data
        - errors: List of validation error messages
    """
    errors = []
    
    # Check if this is financial data
    has_financials = data.get("has_financials", False)
    
    # Check required fields
    for field in COMPANY_SCHEMA["required"]:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: {field}")
    
    # If required fields are missing, return early
    if errors:
        return False, {}, errors
    
    # Check if at least one of features, pricing, metrics, or financials exists
    has_content = any(field in data and data[field] for field in ["features", "pricing", "metrics", "has_financials"])
    if not has_content:
        errors.append("Must have at least one of: features, pricing, metrics, or financial data")
        return False, {}, errors
    
    # Structure the data
    structured_data = {
        "company_name": data.get("company_name", ""),
        "industry": data.get("industry", ""),
        "description": data.get("description", ""),
        "website": data.get("website", ""),
        "product_name": data.get("product_name", ""),
        "target_market": data.get("target_market", ""),
        "founded": data.get("founded", ""),
        "headquarters": data.get("headquarters", ""),
        "features": parse_company_features(data),
        "pricing": parse_company_pricing(data),
        "metrics": data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {},
        "has_financials": has_financials,
        "financial_columns": data.get("financial_columns", [])
    }
    
    return True, structured_data, []


def parse_company_features(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract and structure features from company data
    
    Args:
        data: Raw company data
        
    Returns:
        List of feature dictionaries with name, description, category
    """
    features = data.get("features", [])
    
    if not features:
        return []
    
    structured_features = []
    
    # Handle different feature formats
    if isinstance(features, list):
        for feature in features:
            if isinstance(feature, str):
                # Simple string feature
                structured_features.append({
                    "name": feature,
                    "description": "",
                    "category": ""
                })
            elif isinstance(feature, dict):
                # Already structured feature
                structured_features.append({
                    "name": feature.get("name", ""),
                    "description": feature.get("description", ""),
                    "category": feature.get("category", "")
                })
    
    return structured_features


def parse_company_pricing(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and structure pricing from company data
    
    Args:
        data: Raw company data
        
    Returns:
        Pricing dictionary with tiers array
    """
    pricing = data.get("pricing", {})
    
    if not pricing:
        return {"tiers": []}
    
    tiers = []
    
    # Handle different pricing formats
    if isinstance(pricing, dict):
        # Check if it's already in tiers format
        if "tiers" in pricing and isinstance(pricing["tiers"], list):
            # Already structured
            for tier in pricing["tiers"]:
                tiers.append({
                    "name": tier.get("name", ""),
                    "price": str(tier.get("price", "")),
                    "billing_period": tier.get("billing_period", tier.get("billing", "monthly")),
                    "features": tier.get("features", [])
                })
        else:
            # Pricing is a dict of tier objects (e.g., {"starter": {...}, "pro": {...}})
            for tier_key, tier_data in pricing.items():
                if isinstance(tier_data, dict):
                    tiers.append({
                        "name": tier_data.get("name", tier_key.title()),
                        "price": str(tier_data.get("price", "")),
                        "billing_period": tier_data.get("billing_period", tier_data.get("billing", "monthly")),
                        "features": tier_data.get("features", [])
                    })
    
    return {"tiers": tiers}


def is_financial_data(data: Dict[str, Any]) -> bool:
    """
    Check if data looks like financial data (quarterly reports, etc.)
    
    Args:
        data: Parsed data dictionary (first row from CSV)
        
    Returns:
        True if data appears to be financial data
    """
    # Check if columns contain financial indicators
    columns = list(data.keys())
    columns_lower = [col.lower() for col in columns]
    
    # Count how many financial indicators are present
    financial_count = sum(1 for indicator in FINANCIAL_INDICATORS 
                         if any(indicator in col for col in columns_lower))
    
    # If we have 2+ financial indicators, it's likely financial data
    return financial_count >= 2


def is_company_data(data: Dict[str, Any]) -> bool:
    """
    Quick check if data looks like company data (including financial data)
    
    Args:
        data: Parsed data dictionary
        
    Returns:
        True if data appears to be company data
    """
    # Check if it has the key indicators of company data
    has_company_name = "company_name" in data
    has_industry = "industry" in data
    has_content = any(key in data for key in ["features", "pricing", "metrics", "product_name"])
    
    # Also check if it's financial data
    is_financial = is_financial_data(data)
    
    return has_company_name or (has_industry and has_content) or is_financial


def get_company_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a summary of company data for display
    
    Args:
        data: Structured company data
        
    Returns:
        Summary dictionary with key metrics
    """
    features = data.get("features", [])
    pricing = data.get("pricing", {})
    tiers = pricing.get("tiers", [])
    has_financials = data.get("has_financials", False)
    financial_columns = data.get("financial_columns", [])
    
    summary = {
        "company_name": data.get("company_name", "Unknown"),
        "industry": data.get("industry", "Not specified"),
        "description": data.get("description", "")[:100] + "..." if len(data.get("description", "")) > 100 else data.get("description", ""),
        "features_count": len(features),
        "pricing_tiers_count": len(tiers),
        "has_metrics": bool(data.get("metrics")),
        "website": data.get("website", ""),
        "has_financials": has_financials
    }
    
    # Add financial data info if present
    if has_financials:
        # Identify financial columns
        financial_cols = [col for col in financial_columns 
                         if any(indicator in col.lower() for indicator in FINANCIAL_INDICATORS)]
        summary["financial_columns"] = financial_cols
        summary["data_type"] = "Financial Data"
    
    return summary


def extract_company_from_financials(csv_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Try to extract company name and industry from financial data columns
    
    Args:
        csv_data: First row of CSV data
        
    Returns:
        Dictionary with company_name and industry if found
    """
    result = {}
    
    # Look for company name in columns
    company_columns = ["company_name", "company", "name", "business_name", "organization"]
    for col in company_columns:
        if col in csv_data:
            result["company_name"] = csv_data[col]
            break
    
    # Look for industry in columns
    industry_columns = ["industry", "sector", "category", "market", "business_type"]
    for col in industry_columns:
        if col in csv_data:
            result["industry"] = csv_data[col]
            break
    
    # If no explicit company name, try to infer from filename or use placeholder
    if "company_name" not in result:
        result["company_name"] = "Your Company"  # Will be replaced by filename in upload handler
    
    # If no industry but has financial data, default to "Financial Services"
    if "industry" not in result and is_financial_data(csv_data):
        result["industry"] = "Business"  # Generic industry for financial data
    
    return result


def normalize_csv_to_company_data(csv_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert CSV data to company data format (including financial data)
    
    Args:
        csv_data: Data parsed from CSV with columns
        
    Returns:
        Normalized company data dictionary
    """
    # Try to extract company data from CSV columns
    normalized = {}
    
    # Map common CSV column names to company schema
    column_mappings = {
        "company_name": ["company_name", "company", "name", "business_name"],
        "industry": ["industry", "sector", "category", "market"],
        "description": ["description", "about", "overview", "summary"],
        "website": ["website", "url", "site", "web"],
        "features": ["features", "feature", "capabilities", "functionality"],
        "pricing": ["pricing", "price", "cost", "plans"],
    }
    
    # Extract fields using column mappings
    for schema_field, possible_columns in column_mappings.items():
        for col in possible_columns:
            if col in csv_data:
                normalized[schema_field] = csv_data[col]
                break
    
    # Handle features if it's a comma-separated string
    if "features" in normalized and isinstance(normalized["features"], str):
        normalized["features"] = [f.strip() for f in normalized["features"].split(",")]
    
    # Check if this is financial data
    if is_financial_data(csv_data):
        # Extract company info from financial data
        company_info = extract_company_from_financials(csv_data)
        
        # Merge with normalized data (financial columns take precedence)
        for key, value in company_info.items():
            if key not in normalized or not normalized[key]:
                normalized[key] = value
        
        # Mark that this has financial data
        normalized["has_financials"] = True
        normalized["financial_columns"] = list(csv_data.keys())
    
    return normalized
