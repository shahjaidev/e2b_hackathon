"""Comparison table generation for competitive analysis"""
import os
from typing import Dict, List
from groq import Groq


# Initialize Groq client
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
MODEL = "qwen/qwen3-32b"


def generate_comparison_table(
    company_data: Dict,
    competitors_data: List[Dict]
) -> Dict:
    """
    Generate comparison table from company and competitor data
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        
    Returns:
        {
            "table": comparison table data,
            "advantages": list of competitive advantages,
            "gaps": list of feature gaps,
            "insights": AI-generated insights
        }
    """
    print(f"\n📊 Generating comparison table...")
    print(f"   Your company: {company_data.get('company_name')}")
    print(f"   Competitors: {len(competitors_data)}")
    
    # Build feature comparison
    features_comparison = build_features_comparison(company_data, competitors_data)
    
    # Build pricing comparison
    pricing_comparison = build_pricing_comparison(company_data, competitors_data)
    
    # Identify advantages and gaps
    advantages = identify_advantages(company_data, competitors_data)
    gaps = identify_gaps(company_data, competitors_data)
    
    # Generate AI insights
    insights = generate_insights(company_data, competitors_data, advantages, gaps)
    
    # Build complete comparison
    comparison = {
        "companies": [
            {"name": company_data.get("company_name"), "is_user_company": True}
        ] + [
            {"name": comp.get("company_name"), "is_user_company": False}
            for comp in competitors_data
        ],
        "features_comparison": features_comparison,
        "pricing_comparison": pricing_comparison,
        "advantages": advantages,
        "gaps": gaps,
        "insights": insights
    }
    
    print(f"✅ Comparison table generated")
    print(f"   Features compared: {len(features_comparison)}")
    print(f"   Advantages: {len(advantages)}")
    print(f"   Gaps: {len(gaps)}")
    
    return comparison


def build_features_comparison(company_data: Dict, competitors_data: List[Dict]) -> List[Dict]:
    """
    Build feature comparison matrix
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        
    Returns:
        List of feature comparison dictionaries
    """
    # Collect all unique features
    all_features = {}
    
    # Add user's features
    for feature in company_data.get("features", []):
        feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
        if feature_name:
            all_features[feature_name] = {
                "feature_name": feature_name,
                "category": feature.get("category", "") if isinstance(feature, dict) else "",
                "presence": {company_data.get("company_name"): True}
            }
    
    # Add competitor features
    for comp in competitors_data:
        comp_name = comp.get("company_name")
        for feature in comp.get("features", []):
            feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
            if feature_name:
                if feature_name not in all_features:
                    all_features[feature_name] = {
                        "feature_name": feature_name,
                        "category": feature.get("category", "") if isinstance(feature, dict) else "",
                        "presence": {}
                    }
                all_features[feature_name]["presence"][comp_name] = True
    
    # Fill in missing presence values
    all_companies = [company_data.get("company_name")] + [c.get("company_name") for c in competitors_data]
    for feature_data in all_features.values():
        for company in all_companies:
            if company not in feature_data["presence"]:
                feature_data["presence"][company] = False
    
    return list(all_features.values())


def build_pricing_comparison(company_data: Dict, competitors_data: List[Dict]) -> List[Dict]:
    """
    Build pricing comparison
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        
    Returns:
        List of pricing comparison dictionaries
    """
    pricing_comparison = []
    
    # Add user's pricing
    user_pricing = company_data.get("pricing", {})
    user_tiers = user_pricing.get("tiers", [])
    if user_tiers:
        pricing_comparison.append({
            "company": company_data.get("company_name"),
            "tiers": user_tiers
        })
    
    # Add competitor pricing
    for comp in competitors_data:
        comp_pricing = comp.get("pricing", {})
        comp_tiers = comp_pricing.get("tiers", [])
        if comp_tiers:
            pricing_comparison.append({
                "company": comp.get("company_name"),
                "tiers": comp_tiers
            })
    
    return pricing_comparison


def identify_advantages(company_data: Dict, competitors_data: List[Dict]) -> List[str]:
    """
    Identify features unique to user's company (competitive advantages)
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        
    Returns:
        List of advantage descriptions
    """
    advantages = []
    
    # Get user's features
    user_features = set()
    for feature in company_data.get("features", []):
        feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
        if feature_name:
            user_features.add(feature_name.lower())
    
    # Get all competitor features
    competitor_features = set()
    for comp in competitors_data:
        for feature in comp.get("features", []):
            feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
            if feature_name:
                competitor_features.add(feature_name.lower())
    
    # Find unique features
    unique_features = user_features - competitor_features
    
    for feature in unique_features:
        advantages.append(f"{feature.title()} (unique to your company)")
    
    return advantages


def identify_gaps(company_data: Dict, competitors_data: List[Dict]) -> List[str]:
    """
    Identify features missing in user's company (gaps)
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        
    Returns:
        List of gap descriptions
    """
    gaps = []
    
    # Get user's features
    user_features = set()
    for feature in company_data.get("features", []):
        feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
        if feature_name:
            user_features.add(feature_name.lower())
    
    # Get all competitor features
    competitor_features = set()
    for comp in competitors_data:
        for feature in comp.get("features", []):
            feature_name = feature.get("name", "") if isinstance(feature, dict) else feature
            if feature_name:
                competitor_features.add(feature_name.lower())
    
    # Find missing features
    missing_features = competitor_features - user_features
    
    for feature in missing_features:
        # Count how many competitors have this feature
        count = sum(
            1 for comp in competitors_data
            if any(
                (f.get("name", "") if isinstance(f, dict) else f).lower() == feature
                for f in comp.get("features", [])
            )
        )
        gaps.append(f"{feature.title()} (available in {count}/{len(competitors_data)} competitors)")
    
    return gaps


def generate_insights(
    company_data: Dict,
    competitors_data: List[Dict],
    advantages: List[str],
    gaps: List[str]
) -> str:
    """
    Generate AI insights using Groq
    
    Args:
        company_data: User's company data
        competitors_data: List of competitor data
        advantages: List of advantages
        gaps: List of gaps
        
    Returns:
        Insights text
    """
    print("🤖 Generating AI insights...")
    
    try:
        # Build summary for Groq
        import json
        
        summary = {
            "your_company": {
                "name": company_data.get("company_name"),
                "features_count": len(company_data.get("features", [])),
                "pricing_tiers": len(company_data.get("pricing", {}).get("tiers", []))
            },
            "competitors": [
                {
                    "name": comp.get("company_name"),
                    "features_count": len(comp.get("features", [])),
                    "pricing_tiers": len(comp.get("pricing", {}).get("tiers", []))
                }
                for comp in competitors_data
            ],
            "advantages": advantages[:5],  # Top 5
            "gaps": gaps[:5]  # Top 5
        }
        
        prompt = f"""Analyze this competitive landscape and provide strategic insights.

{json.dumps(summary, indent=2)}

Provide:
1. Market Position Summary (2-3 sentences)
2. Key Strengths (2-3 points)
3. Areas for Improvement (2-3 points)
4. Strategic Recommendations (3-4 actionable items)

Be concise and actionable. Focus on insights that can drive business decisions."""
        
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a competitive intelligence analyst. Provide clear, actionable insights."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=1024
        )
        
        insights = response.choices[0].message.content
        print("✅ Insights generated")
        return insights
        
    except Exception as e:
        print(f"❌ Error generating insights: {e}")
        return "Unable to generate insights at this time."
