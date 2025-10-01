import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import websockets
from aiohttp import web
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Config:
    MISTRAL_API_KEY = "gT5ywZHJuGyiKjwcaTMosRZFahQvPiy9"
    QDRANT_API_KEY = "9ec523db-2424-4e81-aac7-c7f20f755179"
    QDRANT_URL = "https://9ec523db-2424-4e81-aac7-c7f20f755179.eu-west-2-0.aws.cloud.qdrant.io"
    
    # Service configuration
    LISTEN_HOST = "0.0.0.0"
    LISTEN_PORT = 8080
    WEBSOCKET_PORT = 8081
    
    @classmethod
    def get_mistral_key(cls):
        return os.getenv('MISTRAL_API_KEY') or cls.MISTRAL_API_KEY

@dataclass
class CodeChangeRecord:
    """Standardized code change record"""
    user_id: int
    file_path: str
    change_type: str
    previous_version: str
    current_version: str
    created_at: str
    request_id: Optional[str] = None

@dataclass
class TestRecommendation:
    """Standardized test recommendation for external systems"""
    id: str
    description: str
    test_code: str
    test_type: str  # unit, integration, security, performance
    priority: str   # high, medium, low
    language: str
    framework: str

@dataclass
class AnalysisResult:
    """Standardized analysis result for external consumption"""
    request_id: str
    file_path: str
    change_type: str
    risk_score: int  # 1-10
    security_issues: List[str]
    test_recommendations: List[TestRecommendation]
    edge_cases: List[str]
    analysis_timestamp: str
    processing_time_ms: int

class MistralAPIClient:
    """Mistral API client for code analysis"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def analyze_code_change(self, record: CodeChangeRecord) -> Dict[str, Any]:
        """Analyze code change and return structured results"""
        
        # Determine language from file extension
        file_ext = record.file_path.split('.')[-1].lower()
        language_map = {
            'js': 'JavaScript', 'ts': 'TypeScript', 'py': 'Python',
            'cs': 'C#', 'java': 'Java', 'go': 'Go', 'rb': 'Ruby',
            'php': 'PHP', 'cpp': 'C++', 'c': 'C'
        }
        language = language_map.get(file_ext, 'Unknown')
        
        # Framework recommendations by language
        framework_map = {
            'JavaScript': 'Jest', 'TypeScript': 'Jest',
            'Python': 'pytest', 'C#': 'xUnit',
            'Java': 'JUnit', 'Go': 'testing',
            'Ruby': 'RSpec', 'PHP': 'PHPUnit'
        }
        
        prompt = f"""
        Analyze this code change and generate test recommendations:
        
        FILE: {record.file_path}
        LANGUAGE: {language}
        CHANGE TYPE: {record.change_type}
        PREVIOUS: {record.previous_version}
        CURRENT: {record.current_version}
        
        Return a JSON response with this exact structure:
        {{
            "risk_score": 1-10,
            "security_issues": ["issue1", "issue2"],
            "test_recommendations": [
                {{
                    "description": "Clear test description",
                    "test_code": "Complete {language} test code using {framework_map.get(language, 'appropriate framework')}",
                    "test_type": "unit|integration|security|performance",
                    "priority": "high|medium|low"
                }}
            ],
            "edge_cases": ["case1", "case2"],
            "framework": "{framework_map.get(language, 'standard')}"
        }}
        
        Focus on:
        1. Security vulnerabilities (hardcoded secrets, injection risks)
        2. Functional correctness
        3. Edge cases and error handling
        4. Performance implications
        5. Integration points
        
        Generate practical, executable test code.
        """
        
        payload = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
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
                        content = result["choices"][0]["message"]["content"]
                        
                        # Try to parse JSON from response
                        try:
                            # Extract JSON from response (might have markdown formatting)
                            json_start = content.find('{')
                            json_end = content.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_content = content[json_start:json_end]
                                return json.loads(json_content)
                            else:
                                return {"error": "No valid JSON found in response", "raw": content}
                        except json.JSONDecodeError:
                            return {"error": "Failed to parse JSON", "raw": content}
                    else:
                        error_text = await response.text()
                        raise Exception(f"Mistral API error {response.status}: {error_text}")
        
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            return {"error": str(e)}

class CodeChangeListener:
    """Main service that listens for code changes and processes them"""
    
    def __init__(self):
        self.mistral = MistralAPIClient(Config.get_mistral_key())
        self.active_connections: List[websockets.WebSocketServerProtocol] = []
        self.request_counter = 0
    
    def parse_input_json(self, json_data: Dict) -> CodeChangeRecord:
        """Parse various JSON formats into standardized CodeChangeRecord"""
        
        # Handle your current format
        if "record" in json_data:
            record_data = json_data["record"]
            return CodeChangeRecord(
                user_id=record_data.get("user_id", 0),
                file_path=record_data["file_path"],
                change_type=record_data["change_type"],
                previous_version=record_data["previousV"],
                current_version=record_data["currentV"],
                created_at=record_data["created_at"],
                request_id=f"req_{self.request_counter}"
            )
        
        # Handle direct format
        elif "file_path" in json_data:
            return CodeChangeRecord(
                user_id=json_data.get("user_id", 0),
                file_path=json_data["file_path"],
                change_type=json_data["change_type"],
                previous_version=json_data.get("previous_version", ""),
                current_version=json_data["current_version"],
                created_at=json_data.get("created_at", datetime.now().isoformat()),
                request_id=f"req_{self.request_counter}"
            )
        
        else:
            raise ValueError("Unrecognized JSON format")
    
    async def process_change_record(self, json_data: Dict) -> AnalysisResult:
        """Process incoming change record and return standardized result"""
        
        start_time = asyncio.get_event_loop().time()
        self.request_counter += 1
        
        try:
            # Parse input
            record = self.parse_input_json(json_data)
            record.request_id = f"req_{self.request_counter}"
            
            logger.info(f"Processing {record.request_id}: {record.file_path}")
            
            # Analyze with Mistral
            analysis = await self.mistral.analyze_code_change(record)
            
            # Convert to standardized format
            if "error" in analysis:
                # Handle errors gracefully
                result = AnalysisResult(
                    request_id=record.request_id,
                    file_path=record.file_path,
                    change_type=record.change_type,
                    risk_score=5,  # Default medium risk
                    security_issues=[f"Analysis error: {analysis['error']}"],
                    test_recommendations=[],
                    edge_cases=[],
                    analysis_timestamp=datetime.now().isoformat(),
                    processing_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
                )
            else:
                # Process successful analysis
                test_recommendations = []
                for i, test_data in enumerate(analysis.get("test_recommendations", [])):
                    test_rec = TestRecommendation(
                        id=f"{record.request_id}_test_{i+1}",
                        description=test_data.get("description", "Generated test"),
                        test_code=test_data.get("test_code", "// Test code here"),
                        test_type=test_data.get("test_type", "unit"),
                        priority=test_data.get("priority", "medium"),
                        language=record.file_path.split('.')[-1],
                        framework=analysis.get("framework", "standard")
                    )
                    test_recommendations.append(test_rec)
                
                result = AnalysisResult(
                    request_id=record.request_id,
                    file_path=record.file_path,
                    change_type=record.change_type,
                    risk_score=analysis.get("risk_score", 5),
                    security_issues=analysis.get("security_issues", []),
                    test_recommendations=test_recommendations,
                    edge_cases=analysis.get("edge_cases", []),
                    analysis_timestamp=datetime.now().isoformat(),
                    processing_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
                )
            
            logger.info(f"Completed {record.request_id} in {result.processing_time_ms}ms")
            return result
            
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            result = AnalysisResult(
                request_id=f"req_{self.request_counter}",
                file_path=json_data.get("file_path", "unknown"),
                change_type=json_data.get("change_type", "unknown"),
                risk_score=8,  # High risk for processing errors
                security_issues=[f"Processing error: {str(e)}"],
                test_recommendations=[],
                edge_cases=[],
                analysis_timestamp=datetime.now().isoformat(),
                processing_time_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
            return result

    # HTTP REST API endpoint
    async def handle_http_request(self, request):
        """Handle HTTP POST requests with JSON"""
        try:
            json_data = await request.json()
            result = await self.process_change_record(json_data)
            
            # Broadcast to WebSocket clients
            await self.broadcast_to_websockets(result)
            
            return web.json_response(asdict(result))
            
        except Exception as e:
            logger.error(f"HTTP request error: {e}")
            return web.json_response(
                {"error": str(e)}, 
                status=400
            )

    # WebSocket handler
    async def handle_websocket(self, websocket, path):
        """Handle WebSocket connections"""
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")
        
        try:
            async for message in websocket:
                try:
                    json_data = json.loads(message)
                    result = await self.process_change_record(json_data)
                    
                    # Send result back to this client
                    await websocket.send(json.dumps(asdict(result)))
                    
                    # Broadcast to other clients
                    await self.broadcast_to_websockets(result, exclude=websocket)
                    
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"error": "Invalid JSON"}))
                except Exception as e:
                    await websocket.send(json.dumps({"error": str(e)}))
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast_to_websockets(self, result: AnalysisResult, exclude=None):
        """Broadcast analysis result to all connected WebSocket clients"""
        if not self.active_connections:
            return
            
        message = json.dumps(asdict(result))
        disconnected = []
        
        for websocket in self.active_connections:
            if websocket == exclude:
                continue
                
            try:
                await websocket.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.active_connections.remove(websocket)

    async def start_http_server(self):
        """Start HTTP REST API server"""
        app = web.Application()
        app.router.add_post('/analyze', self.handle_http_request)
        app.router.add_get('/health', lambda r: web.Response(text="OK"))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, Config.LISTEN_HOST, Config.LISTEN_PORT)
        await site.start()
        
        logger.info(f"HTTP server started on {Config.LISTEN_HOST}:{Config.LISTEN_PORT}")
        logger.info(f"Send POST requests to: http://{Config.LISTEN_HOST}:{Config.LISTEN_PORT}/analyze")

    async def start_websocket_server(self):
        """Start WebSocket server"""
        server = await websockets.serve(
            self.handle_websocket,
            Config.LISTEN_HOST,
            Config.WEBSOCKET_PORT
        )
        
        logger.info(f"WebSocket server started on {Config.LISTEN_HOST}:{Config.WEBSOCKET_PORT}")
        logger.info(f"Connect via: ws://{Config.LISTEN_HOST}:{Config.WEBSOCKET_PORT}")
        
        return server

    async def run(self):
        """Run both HTTP and WebSocket servers"""
        logger.info("Starting Code Change Listener Service...")
        
        # Start both servers
        await self.start_http_server()
        websocket_server = await self.start_websocket_server()
        
        logger.info("Service is running. Listening for code changes...")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running
        try:
            await websocket_server.wait_closed()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            websocket_server.close()
            await websocket_server.wait_closed()

# Test client functions
async def test_http_client():
    """Test the HTTP endpoint"""
    test_data = {
        "record": {
            "user_id": 2,
            "file_path": "src/services/auth.js",
            "change_type": "added",
            "previousV": "empty",
            "currentV": "export function login(user, pass) { return user === 'admin' && pass === '1234'; }",
            "created_at": "2025-09-19T20:23:33.801Z"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post('http://localhost:8080/analyze', json=test_data) as response:
            result = await response.json()
            print("HTTP Response:")
            print(json.dumps(result, indent=2))

async def test_websocket_client():
    """Test the WebSocket endpoint"""
    test_data = {
        "file_path": "src/api/user.py",
        "change_type": "modified",
        "previous_version": "def get_user(): return {}",
        "current_version": "def get_user(id): return db.query(f'SELECT * FROM users WHERE id={id}')",
        "user_id": 1
    }
    
    async with websockets.connect('ws://localhost:8081') as websocket:
        # Send test data
        await websocket.send(json.dumps(test_data))
        
        # Receive response
        response = await websocket.recv()
        result = json.loads(response)
        
        print("WebSocket Response:")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test-http":
            asyncio.run(test_http_client())
        elif sys.argv[1] == "test-websocket":
            asyncio.run(test_websocket_client())
        else:
            print("Usage: python script.py [test-http|test-websocket]")
    else:
        # Run the main service
        listener = CodeChangeListener()
        asyncio.run(listener.run())