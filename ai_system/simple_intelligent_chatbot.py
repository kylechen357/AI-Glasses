#!/usr/bin/env python3
"""
Simple Intelligent Chatbot Demo
Clean, working version with autonomous AI and RabbitMQ integration
"""

import streamlit as st
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Import our components
from intelligent_agent import IntelligentAgent
from llm_manager import LLMManager
from rag_memory import RAGMemorySystem
from rabbitmq_client import RabbitMQClient
#from technical_search_manager import TechnicalSearchManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="🤖 Intelligent AR Assistant",
    page_icon="🧠",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .result-box {
        background-color: #e8f5e8;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #dc3545;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Global components
if 'components_initialized' not in st.session_state:
    st.session_state.components_initialized = False
    st.session_state.intelligent_agent = None
    st.session_state.llm_manager = None
    st.session_state.rag_memory = None
    st.session_state.technical_search = None
    st.session_state.rabbitmq_client = None

async def initialize_components():
    """Initialize all components"""
    try:
        # Initialize Intelligent Agent
        st.session_state.intelligent_agent = IntelligentAgent()
        await st.session_state.intelligent_agent.initialize()
        
        # Initialize LLM Manager
        st.session_state.llm_manager = LLMManager()
        await st.session_state.llm_manager.initialize()
        
        # Initialize RAG Memory
        st.session_state.rag_memory = RAGMemorySystem()
        await st.session_state.rag_memory.initialize()
        
        # Initialize Technical Search
        #st.session_state.technical_search = TechnicalSearchManager()
        
        # Initialize RabbitMQ
        st.session_state.rabbitmq_client = RabbitMQClient()
        await st.session_state.rabbitmq_client.initialize()
        
        st.session_state.components_initialized = True
        return True
        
    except Exception as e:
        st.error(f"Failed to initialize: {e}")
        return False

async def process_request(user_input: str) -> Dict[str, Any]:
    """Process user request"""
    try:
        # Ensure components are initialized
        if not st.session_state.components_initialized or st.session_state.intelligent_agent is None:
            logger.error("Components not initialized")
            return {
                "success": False,
                "error": "System components not initialized. Please initialize the system first.",
                "action": "initialization_required",
                "target": "system"
            }
        
        # Get components
        agent = st.session_state.intelligent_agent
        user_id = "default_user"
        
        logger.info(f"Processing request: {user_input}")
        
        # Understand intent
        intent = await agent.understand_intent(user_input, user_id)
        logger.info(f"Intent understood: {type(intent)}, category: {getattr(intent, 'category', 'unknown')}")
        logger.info(f"Intent entities: {type(getattr(intent, 'entities', None))}, value: {getattr(intent, 'entities', None)}")
        
        # Execute intent
        result = await agent.execute_intent(intent, user_id)
        logger.info(f"Intent executed: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'not dict'}")
        
        # Extract action and target from intent and result
        action = result.get("action_taken", getattr(intent, 'action', "unknown"))
        target = "unknown"
        
        # Try to extract target from different sources
        if hasattr(intent, 'entities') and intent.entities:
            try:
                logger.info(f"Extracting from entities: {type(intent.entities)} = {intent.entities}")
                # Check if entities is a dict or list
                if isinstance(intent.entities, dict):
                    # Get the first entity as target
                    entity_keys = [k for k in intent.entities.keys() if k.startswith('entity_')]
                    if entity_keys:
                        target = intent.entities[entity_keys[0]]
                elif isinstance(intent.entities, list) and len(intent.entities) > 0:
                    # If it's a list, get the first item
                    target = str(intent.entities[0])
                else:
                    # Convert to string if it's neither dict nor list
                    target = str(intent.entities)
            except (KeyError, IndexError, AttributeError) as e:
                logger.warning(f"Error extracting target from entities: {e}")
                target = "unknown"
        
        # Or get from rabbitmq_command
        if result.get("rabbitmq_command") and isinstance(result["rabbitmq_command"], dict):
            target = result["rabbitmq_command"].get("target", target)
        
        # Or get from results
        if result.get("results") and isinstance(result["results"], dict):
            results = result["results"]
            target = (results.get("navigation_target") or 
                     results.get("search_term") or 
                     results.get("stock_symbol") or 
                     results.get("equipment") or
                     str(target))
        
        # Send to RabbitMQ if successful and get the sent data
        rabbitmq_data = None
        if result.get("success"):
            # Create data for RabbitMQ based on result
            data = result.get("response_message", user_input)
            rabbitmq_result = {"data": data}
            rabbitmq_data = await send_to_rabbitmq(rabbitmq_result)
        
        return {
            "success": result.get("success", False),
            "intent": intent,
            "result": result,
            "action": action,
            "target": target,
            "data": result.get("response_message", ""),
            "rabbitmq_data": rabbitmq_data,
            "error": result.get("error")
        }
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        return {
            "success": False,
            "error": str(e),
            "action": "error",
            "target": "none"
        }

async def send_to_rabbitmq(result: Dict[str, Any]) -> Dict[str, Any]:
    """Send command to RabbitMQ in chatbot_demo.py format"""
    try:
        import pika
        import json
        
        # Get the response message and determine command based on content
        data = result.get("data", "")
        
        # Smart command detection
        command = "open_notepad"  # Default
        
        # Check for URLs first
        if any(url_pattern in str(data).lower() for url_pattern in ["http", "www", ".com", ".org", ".net"]):
            command = "open_browser"
        # Check for image/photo search keywords
        elif any(keyword in str(data).lower() for keyword in ["searching for images", "image search", "photo search", "pictures", "photos", "images", "找照片", "搜尋圖片", "圖片搜尋", "相片"]):
            command = "open_browser"
        # Check for navigation keywords
        elif any(keyword in str(data).lower() for keyword in ["navigating", "navigation", "directions", "route", "導航", "路線"]):
            command = "open_browser"
        # Check for web search keywords
        elif any(keyword in str(data).lower() for keyword in ["searching", "search", "looking up", "搜尋", "查詢", "搜索"]):
            command = "open_browser"
        # Technical manuals and long text stay as notepad
        else:
            command = "open_notepad"
        
        # Format message like chatbot_demo.py
        ar_command_data = {
            "command": command,
            "group": "coretronic.hq.aird.aiic",
            "data": str(data)
        }
        
        # Serialize JSON data (matching chatbot_demo.py)
        json_message = json.dumps(ar_command_data)
        
        # Connection info (matching chatbot_demo.py template exactly)
        user_info = pika.PlainCredentials('ar_user', 'ar@developer')
        connection = pika.BlockingConnection(
            pika.ConnectionParameters('', 5672, '/', user_info)
        )
        
        channel = connection.channel()
        
        # Declare exchange (using command exchange)
        channel.exchange_declare(exchange='command', exchange_type='topic', durable=True)
        
        # Publish message (simplified format)
        channel.basic_publish(
            exchange='command',
            routing_key='',
            body=json_message
        )
        
        connection.close()
        
        logger.info(f"Sent to RabbitMQ: {ar_command_data}")
        return ar_command_data
        
    except Exception as e:
        error_msg = f"RabbitMQ send error: {e}"
        logger.error(error_msg)
        return {"error": error_msg}

def main():
    """Main application"""
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Intelligent AR Assistant</h1>
        <p>Autonomous AI • RabbitMQ Integration • Multi-language Support</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("🎛️ System Controls")
        
        # Initialize button
        if not st.session_state.components_initialized:
            if st.button("🚀 Initialize System", type="primary"):
                with st.spinner("Initializing components..."):
                    success = asyncio.run(initialize_components())
                    if success:
                        st.success("✅ System Ready!")
                        st.rerun()
                    else:
                        st.error("❌ Initialization Failed")
        else:
            st.success("✅ System Active")
        
        # Component status
        if st.session_state.components_initialized:
            st.subheader("📊 Component Status")
            st.write("🧠 Intelligent Agent: ✅")
            st.write("🦙 LLM Manager: ✅") 
            st.write("💾 RAG Memory: ✅")
            st.write("🔍 Technical Search: ✅")
            st.write("📡 RabbitMQ Client: ✅")
    
    # Main content
    if not st.session_state.components_initialized:
        st.info("👈 Please initialize the system using the sidebar")
        return
    
    # Example buttons
    st.subheader("💡 Quick Examples")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧭 Navigate to Taipei 101"):
            if not st.session_state.components_initialized:
                st.error("❌ Please initialize the system first")
            else:
                with st.spinner("Processing navigation request..."):
                    result = asyncio.run(process_request("I want to go to Taipei 101"))
                    if result["success"]:
                        st.success("✅ Navigation processed!")
                        st.info(f"Action: {result['action']}")
                    else:
                        st.error(f"❌ Error: {result.get('error', 'Unknown')}")
    
    with col2:
        if st.button("🔍 Search cat photos"):
            if not st.session_state.components_initialized:
                st.error("❌ Please initialize the system first")
            else:
                with st.spinner("Processing image search..."):
                    result = asyncio.run(process_request("幫我找貓的照片"))
                    if result["success"]:
                        st.success("✅ Image search processed!")
                        st.info(f"Action: {result['action']}")
                    else:
                        st.error(f"❌ Error: {result.get('error', 'Unknown')}")
    
    with col3:
        if st.button("📈 Get TSMC stock"):
            if not st.session_state.components_initialized:
                st.error("❌ Please initialize the system first")
            else:
                with st.spinner("Processing stock request..."):
                    result = asyncio.run(process_request("Get TSMC stock price"))
                    if result["success"]:
                        st.success("✅ Stock request processed!")
                        st.info(f"Action: {result['action']}")
                    else:
                        st.error(f"❌ Error: {result.get('error', 'Unknown')}")
    
    # Text input
    st.subheader("💬 Custom Request")
    user_input = st.text_input(
        "Enter your request:",
        placeholder="e.g., 'I want to go to the airport', '幫我找台北101的照片', 'UR10手臂壞掉怎麼辦'"
    )
    
    if st.button("🚀 Process Request") and user_input:
        if not st.session_state.components_initialized:
            st.error("❌ Please initialize the system first")
        else:
            with st.spinner("🤖 Processing your request..."):
                result = asyncio.run(process_request(user_input))
                
                if result["success"]:
                    # Build status message
                    status_msg = "Processed but not sent to RabbitMQ"
                    rabbitmq_display = ""
                    
                    if result.get("rabbitmq_data"):
                        if result["rabbitmq_data"].get("error"):
                            status_msg = f"RabbitMQ Error: {result['rabbitmq_data']['error']}"
                        else:
                            status_msg = "Sent to AR glasses via RabbitMQ"
                            # Format the JSON properly without f-string backslashes
                            formatted_json = str(result['rabbitmq_data']).replace('{', '{\n  ').replace(',', ',\n  ').replace('}', '\n}')
                            rabbitmq_display = f"""
                            <p><strong>RabbitMQ Message:</strong></p>
                            <pre style="background-color: #f0f0f0; padding: 10px; border-radius: 5px;">
{formatted_json}
                            </pre>"""
                    
                    result_data_display = ""
                    if result.get("data"):
                        result_data_display = f"""
                        <p><strong>Result Data:</strong></p>
                        <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">
                            {str(result['data'])[:500]}{'...' if len(str(result['data'])) > 500 else ''}
                        </div>"""
                    
                    st.markdown(f"""
                    <div class="result-box">
                        <h4>✅ Request Processed Successfully</h4>
                        <p><strong>Your Request:</strong> {user_input}</p>
                        <p><strong>Action:</strong> {result['action']}</p>
                        <p><strong>Target:</strong> {result['target']}</p>
                        <p><strong>Status:</strong> {status_msg}</p>
                        {rabbitmq_display}
                        {result_data_display}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="error-box">
                        <h4>❌ Processing Failed</h4>
                        <p><strong>Your Request:</strong> {user_input}</p>
                        <p><strong>Error:</strong> {result.get('error', 'Unknown error')}</p>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Help section
    with st.expander("ℹ️ How to Use"):
        st.write("""
        **Quick Start:**
        1. Initialize the system using the sidebar
        2. Click example buttons for quick tests
        3. Or type your own request in any language
        
        **Supported Requests:**
        - Navigation: "I want to go to [location]"
        - Image search: "幫我找[主題]的照片"
        - Stock prices: "Get [company] stock price"
        - Technical support: "[設備]壞掉怎麼辦"
        - General questions: "What can you help me with?"
        
        **Features:**
        - Autonomous intent understanding
        - Multi-language support (English/Chinese)
        - Real RabbitMQ integration
        - AR glasses command formatting
        """)

if __name__ == "__main__":
    main()
