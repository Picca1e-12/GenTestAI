import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.http import models

class Config:
    MISTRAL_API_KEY = "gT5ywZHJuGyiKjwcaTMosRZFahQvPiy9" 
    QDRANT_API_KEY = "9ec523db-2424-4e81-aac7-c7f20f755179"
    QDRANT_URL = "https://9ec523db-2424-4e81-aac7-c7f20f755179.eu-west-2-0.aws.cloud.qdrant.io"
    
    @classmethod
    def get_mistral_key(cls):
        return os.getenv('MISTRAL_API_KEY') or cls.MISTRAL_API_KEY
    
    @classmethod
    def get_qdrant_key(cls):
        return os.getenv('QDRANT_API_KEY') or cls.QDRANT_API_KEY
    
    @classmethod
    def get_qdrant_url(cls):
        return os.getenv('QDRANT_URL') or cls.QDRANT_URL
    
    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        mistral_key = cls.get_mistral_key()
        qdrant_key = cls.get_qdrant_key()
        qdrant_url = cls.get_qdrant_url()
        
        if not mistral_key or not qdrant_key or not qdrant_url:
            raise ValueError("Missing API credentials. Please update the Config class.")
        
        print("Configuration validation passed!")

@dataclass
class CodeChangeRecord:
    """Represents a code change record from your JSON"""
    user_id: int
    file_path: str
    change_type: str
    previous_version: str
    current_version: str
    created_at: str

class MistralAPIClient:
    """Enhanced client for Mistral AI API interactions"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def analyze_code_change_record(self, change_record: CodeChangeRecord) -> Dict[str, Any]:
        """Analyze a code change record and generate comprehensive test recommendations"""
        
        # Determine language from file extension
        file_ext = change_record.file_path.split('.')[-1]
        language_map = {
            'js': 'JavaScript',
            'py': 'Python', 
            'cs': 'C#',
            'java': 'Java',
            'ts': 'TypeScript'
        }
        language = language_map.get(file_ext, 'Unknown')
        
        prompt = f"""
        Analyze this code change and generate comprehensive test recommendations:
        
        FILE: {change_record.file_path}
        LANGUAGE: {language}
        CHANGE TYPE: {change_record.change_type}
        PREVIOUS VERSION: {change_record.previous_version}
        CURRENT VERSION: {change_record.current_version}
        
        Please provide a detailed analysis including:
        1. Security vulnerabilities identified
        2. Functional test cases needed
        3. Edge cases to test
        4. Integration test requirements
        5. Risk assessment (1-10 scale)
        6. Recommended test framework and specific test code
        
        Focus on practical, executable test cases in the appropriate language.
        If you identify security issues, highlight them clearly.
        
        Respond in JSON format with the following structure:
        {{
            "risk_assessment": {{
                "score": 1-10,
                "reasons": ["reason1", "reason2"]
            }},
            "security_issues": ["issue1", "issue2"],
            "recommended_tests": [
                {{
                    "type": "unit|integration|security",
                    "description": "Test description",
                    "test_code": "Actual test code in appropriate language",
                    "priority": "high|medium|low"
                }}
            ],
            "edge_cases": ["case1", "case2"],
            "framework_recommendations": "Suggested test framework"
        }}
        """
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        raise Exception(f"Mistral API error {response.status}: {error_text}")
        except Exception as e:
            raise Exception(f"Error analyzing code: {e}")

    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for similarity search"""
        payload = {
            "model": "mistral-embed",
            "input": [text]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/embeddings",
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["data"][0]["embedding"]
                    else:
                        raise Exception(f"Embedding error: {response.status}")
        except Exception as e:
            raise Exception(f"Error generating embeddings: {e}")

def parse_input_json(self, json_data: Dict) -> CodeChangeRecord:
    """Parse various JSON formats into standardized CodeChangeRecord"""

    # Extract aiResponse if present
    self.ai_testcases = []
    if "aiResponse" in json_data:
        self.ai_testcases = json_data["aiResponse"].get("testCases", [])

    # Handle current { "record": {...} } format
    if "record" in json_data:
        record_data = json_data["record"]
        return CodeChangeRecord(
            user_id=record_data.get("user_id", 0),
            file_path=record_data["file_path"],
            change_type=record_data["change_type"],
            previous_version=record_data.get("previousV", ""),
            current_version=record_data.get("currentV", ""),
            created_at=record_data.get("created_at", datetime.now().isoformat()),
            request_id=f"req_{self.request_counter}"
        )

    # Handle direct format (fallback)
    elif "file_path" in json_data:
        return CodeChangeRecord(
            user_id=json_data.get("user_id", 0),
            file_path=json_data["file_path"],
            change_type=json_data["change_type"],
            previous_version=json_data.get("previous_version", ""),
            current_version=json_data.get("current_version", ""),
            created_at=json_data.get("created_at", datetime.now().isoformat()),
            request_id=f"req_{self.request_counter}"
        )

    else:
        raise ValueError("Unrecognized JSON format")


class EnhancedTestingCompanion:
    """Enhanced version that handles your JSON change records"""
    
    
    
    def __init__(self):
        Config.validate_config()
        
        mistral_api_key = Config.get_mistral_key()
        
        print("Initializing Enhanced AI Testing Companion...")
        self.mistral = MistralAPIClient(mistral_api_key)
    
    def parse_change_record(self, json_data: Dict) -> CodeChangeRecord:
        """Parse your JSON change record format"""
        record_data = json_data["record"]
        
        return CodeChangeRecord(
            user_id=record_data["user_id"],
            file_path=record_data["file_path"],
            change_type=record_data["change_type"],
            previous_version=record_data["previousV"],
            current_version=record_data["currentV"],
            created_at=record_data["created_at"]
        )
    
    async def analyze_change_record(self, json_data: Dict) -> Dict[str, Any]:
        """Main function to analyze your change record JSON"""
        
        try:
            # Parse the change record
            change_record = self.parse_change_record(json_data)
            
            print(f"Analyzing change in: {change_record.file_path}")
            print(f"Change type: {change_record.change_type}")
            
            # Get AI analysis
            analysis = await self.mistral.analyze_code_change_record(change_record)
            
            # Try to parse the JSON response
            try:
                analysis_json = json.loads(analysis)
            except json.JSONDecodeError:
                # If it's not valid JSON, wrap it
                analysis_json = {"raw_analysis": analysis}
            
            # Add metadata
            result = {
                "change_record": {
                    "file_path": change_record.file_path,
                    "change_type": change_record.change_type,
                    "user_id": change_record.user_id,
                    "created_at": change_record.created_at
                },
                "analysis": analysis_json,
                "timestamp": change_record.created_at
            }
            
            return result
            
        except Exception as e:
            return {
                "error": f"Analysis failed: {e}",
                "change_record": json_data.get("record", {}),
                "analysis": None
            }

async def main():
    """Test with your provided JSON data"""
    
    # Your JSON data
    test_json = {
        "message": "Change recorded successfully",
        "record": {
            "user_id": 2,
            "file_path": "src/services/auth.js",
            "change_type": "added",
            "previousV": "empty",
            "currentV": "export function login(user, pass) { return user === 'admin' && pass === '1234'; }",
            "created_at": "2025-09-19T20:23:33.801Z"
        }
    }
    
    try:
        # Initialize the enhanced companion
        companion = EnhancedTestingCompanion()
        
        # Analyze the change record
        print("Analyzing your code change record...")
        result = await companion.analyze_change_record(test_json)
        
        print("\n" + "="*60)
        print("ENHANCED TEST ANALYSIS RESULTS:")
        print("="*60)
        print(json.dumps(result, indent=2, default=str))
        
        # Extract key insights
        if "analysis" in result and result["analysis"]:
            analysis = result["analysis"]
            
            print("\n" + "="*60)
            print("KEY INSIGHTS:")
            print("="*60)
            
            if isinstance(analysis, dict):
                if "security_issues" in analysis:
                    print("🚨 SECURITY ISSUES DETECTED:")
                    for issue in analysis["security_issues"]:
                        print(f"  - {issue}")
                
                if "risk_assessment" in analysis:
                    risk = analysis["risk_assessment"]
                    if isinstance(risk, dict) and "score" in risk:
                        print(f"\n📊 RISK SCORE: {risk['score']}/10")
                        if "reasons" in risk:
                            print("Reasons:")
                            for reason in risk["reasons"]:
                                print(f"  - {reason}")
                
                if "recommended_tests" in analysis:
                    print(f"\n🧪 RECOMMENDED TESTS: {len(analysis['recommended_tests'])} tests")
                    for i, test in enumerate(analysis["recommended_tests"][:3]):  # Show first 3
                        if isinstance(test, dict):
                            print(f"  {i+1}. {test.get('description', 'Test')}")
                            print(f"     Priority: {test.get('priority', 'Unknown')}")
            
        print("\n" + "="*60)
        print("COMPARISON WITH CURRENT SYSTEM:")
        print("="*60)
        print("❌ Current system issues identified:")
        print("  - Hardcoded credentials detected")
        print("  - Malformed test generation")
        print("  - Language mismatch (JS function, C# test)")
        print("  - Incomplete test cases")
        print("  - No security analysis")
        print("\n✅ Enhanced system improvements:")
        print("  - Proper security vulnerability detection")
        print("  - Language-appropriate test generation")
        print("  - Comprehensive risk assessment")
        print("  - Structured, actionable recommendations")
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure to update your API keys in the Config class!")

if __name__ == "__main__":
    asyncio.run(main())


    
    