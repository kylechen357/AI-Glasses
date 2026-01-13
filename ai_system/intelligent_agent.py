"""
Intelligent Agent System
Autonomous decision-making AI that understands context and user intent
without requiring explicit definitions in code
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum

try:
    from .config import config
    from .llm_manager import llm_manager
    from .mcp_manager import mcp_manager
    from .rag_memory import RAGMemorySystem
except ImportError:
    from config import config
    from llm_manager import llm_manager
    from mcp_manager import mcp_manager
    from rag_memory import RAGMemorySystem

logger = logging.getLogger(__name__)

class IntentCategory(Enum):
    """Categories of user intents the system can handle"""
    NAVIGATION = "navigation"
    SEARCH = "search"
    INFORMATION = "information"
    CONTROL = "control"
    COMMUNICATION = "communication"
    ENTERTAINMENT = "entertainment"
    PRODUCTIVITY = "productivity"
    LEARNING = "learning"
    TECHNICAL_SUPPORT = "technical_support"
    UNKNOWN = "unknown"

@dataclass
class UserIntent:
    """Represents understood user intent"""
    category: IntentCategory
    action: str
    entities: Dict[str, Any]
    confidence: float
    context: Dict[str, Any]
    suggested_tools: List[str]
    execution_plan: List[Dict[str, Any]]

@dataclass
class ConversationContext:
    """Maintains conversation context and history"""
    user_id: str
    session_id: str
    history: List[Dict[str, Any]]
    current_topic: Optional[str]
    user_preferences: Dict[str, Any]
    last_action: Optional[str]
    context_embeddings: Optional[List[float]]

class IntelligentAgent:
    """
    Autonomous AI agent that understands user intent and context
    without requiring explicit programming for each scenario
    """
    
    def __init__(self):
        self.rag_memory = RAGMemorySystem()
        self.conversation_contexts: Dict[str, ConversationContext] = {}
        self.intent_patterns = self._initialize_intent_patterns()
        self.tool_capabilities = {}
        self.learning_data = []
        
    async def initialize(self):
        """Initialize the intelligent agent"""
        logger.info("Initializing Intelligent Agent...")
        
        # Initialize dependencies
        await self.rag_memory.initialize()
        
        # Load tool capabilities
        await self._discover_tool_capabilities()
        
        # Load conversation patterns from memory
        await self._load_learned_patterns()
        
        logger.info("Intelligent Agent initialized successfully")
    
    def _initialize_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize base intent recognition patterns"""
        return {
            IntentCategory.NAVIGATION.value: [
                r'(?:go|take me|navigate|drive|walk) (?:to|towards?) (.+)',
                r'(?:find|locate|show me) (?:the )?(?:way|route|direction) (?:to|towards?) (.+)',
                r'(?:how (?:do|can) i get (?:to|towards?)) (.+)',
                r'(?:where is|location of) (.+)',
                r'我要去(.+)', r'帶我去(.+)', r'導航到(.+)', r'去(.+)',
            ],
            IntentCategory.SEARCH.value: [
                r'(?:search|find|look (?:up|for)|google) (.+)',
                r'(?:what|who|when|where|why|how) (?:is|are|was|were|do|does|did) (.+)',
                r'(?:tell me about|information about|explain) (.+)',
                r'(?:show me|find me) (?:pictures?|images?|photos?) (?:of|about) (.+)',
                r'搜尋(.+)', r'找(.+)', r'查(.+)', r'幫我找(.+)的(?:照片|圖片|相片)',
            ],
            IntentCategory.INFORMATION.value: [
                r'(?:what|how much) (?:is|are) (?:the )?(.+) (?:stock|price|cost)',
                r'(?:get|show|check) (?:me )?(?:the )?(.+) (?:stock|price|quote)',
                r'(?:weather|temperature) (?:in|at|for) (.+)',
                r'(?:news|headlines) (?:about|on) (.+)',
                r'(.+)(?:的股價|股票|價格)', r'查看(.+)股票',
            ],
            IntentCategory.CONTROL.value: [
                r'(?:open|launch|start|run) (.+)',
                r'(?:close|stop|end|quit) (.+)',
                r'(?:turn (?:on|off)|enable|disable) (.+)',
                r'(?:set|change|adjust) (.+) (?:to|as) (.+)',
                r'打開(.+)', r'關閉(.+)', r'啟動(.+)', r'停止(.+)',
            ],
            IntentCategory.COMMUNICATION.value: [
                r'(?:send|text|message|email|call) (.+)',
                r'(?:reply|respond) (?:to|with) (.+)',
                r'(?:schedule|book|arrange) (.+) (?:meeting|appointment|call)',
                r'發送(.+)', r'傳送(.+)', r'回覆(.+)', r'安排(.+)',
            ],
            IntentCategory.ENTERTAINMENT.value: [
                r'(?:play|watch|listen to|stream) (.+)',
                r'(?:recommend|suggest) (?:me )?(?:some |a )?(.+)',
                r'(?:what|any) (?:good |new )?(.+) (?:to (?:watch|listen|read|play))',
                r'播放(.+)', r'觀看(.+)', r'聽(.+)', r'推薦(.+)',
            ],
            IntentCategory.PRODUCTIVITY.value: [
                r'(?:create|make|write|draft) (?:a |an )?(.+)',
                r'(?:save|store|backup) (.+) (?:to|in|as) (.+)',
                r'(?:schedule|plan|organize) (.+)',
                r'(?:remind me|set reminder) (?:to|about) (.+)',
                r'創建(.+)', r'製作(.+)', r'儲存(.+)', r'安排(.+)', r'提醒(.+)',
            ],
            IntentCategory.TECHNICAL_SUPPORT.value: [
                r'(.+) (?:壞掉|故障|出問題|不能用|無法使用) (?:怎麼辦|如何處理)',
                r'(.+) (?:broken|not working|malfunctioning|error|problem|issue)',
                r'(?:how to (?:fix|repair|troubleshoot)) (.+)',
                r'(?:problem with|issue with|trouble with) (.+)',
                r'(.+) (?:維修|修理|故障排除)',
                r'(?:error|fault|alarm) (?:on|in|with) (.+)',
                r'(.+) (?:stopped working|won\'t start|won\'t turn on)',
                r'(?:diagnostic|diagnosis) (?:for|of) (.+)',
                r'(.+) (?:manual|documentation|service guide)',
                r'(?:UR\d+|robot|robotic arm|industrial equipment) (.+)',
            ],
        }
    
    async def _discover_tool_capabilities(self):
        """Discover available tool capabilities"""
        try:
            # Get MCP server status and capabilities
            server_status = await mcp_manager.get_server_status()
            
            self.tool_capabilities = {
                "web-search": {
                    "can_search_web": True,
                    "can_find_images": True,
                    "can_open_websites": True,
                    "can_get_directions": True,
                },
                "stock-checker": {
                    "can_get_stock_prices": True,
                    "can_track_markets": True,
                    "can_analyze_trends": True,
                },
                "filesystem": {
                    "can_read_files": True,
                    "can_write_files": True,
                    "can_list_directories": True,
                    "can_manage_data": True,
                },
                "rag-memory": {
                    "can_remember_conversations": True,
                    "can_learn_preferences": True,
                    "can_provide_context": True,
                    "can_answer_from_memory": True,
                }
            }
            
            logger.info(f"Discovered tool capabilities: {list(self.tool_capabilities.keys())}")
            
        except Exception as e:
            logger.error(f"Error discovering tool capabilities: {e}")
    
    async def _load_learned_patterns(self):
        """Load previously learned conversation patterns"""
        try:
            # Query RAG memory for learned patterns
            learned_patterns = await self.rag_memory.query(
                "conversation patterns intent recognition user behavior",
                k=10
            )
            
            # Process and integrate learned patterns
            for result in learned_patterns:
                content = result.get('content', '')
                if 'intent_pattern' in content:
                    # Parse and add to pattern database
                    # This would be more sophisticated in practice
                    pass
                    
        except Exception as e:
            logger.debug(f"No learned patterns found or error loading: {e}")
    
    async def understand_intent(
        self,
        user_input: str,
        user_id: str = "default",
        context: Dict[str, Any] = None
    ) -> UserIntent:
        """
        Understand user intent using multiple approaches:
        1. Pattern matching
        2. LLM-based intent recognition
        3. Context analysis
        4. Historical behavior
        """
        
        # Get or create conversation context
        conv_context = self._get_conversation_context(user_id)
        
        # Enhance with provided context
        if context:
            conv_context.context_embeddings = context.get('embeddings')
        
        # Add current input to history
        conv_context.history.append({
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "type": "user"
        })
        
        # Step 1: Pattern-based intent recognition
        pattern_intent = await self._match_intent_patterns(user_input)
        
        # Step 2: LLM-based sophisticated understanding
        llm_intent = await self._llm_intent_analysis(
            user_input,
            conv_context,
            pattern_intent
        )
        
        # Step 3: Context-aware enhancement
        enhanced_intent = await self._enhance_with_context(
            llm_intent,
            conv_context,
            user_input  # Pass original input for context
        )
        
        # Step 4: Learn from this interaction
        await self._learn_from_interaction(user_input, enhanced_intent)
        
        return enhanced_intent
    
    async def _match_intent_patterns(self, user_input: str) -> Optional[Tuple[IntentCategory, Dict[str, Any]]]:
        """Match user input against known patterns"""
        user_input_lower = user_input.lower().strip()
        
        for category_name, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, user_input_lower, re.IGNORECASE)
                if match:
                    entities = {f"entity_{i}": group for i, group in enumerate(match.groups())}
                    return IntentCategory(category_name), entities
        
        return None
    
    async def _llm_intent_analysis(
        self,
        user_input: str,
        conv_context: ConversationContext,
        pattern_result: Optional[Tuple]
    ) -> UserIntent:
        """Use LLM for sophisticated intent understanding"""
        
        # Build context-aware prompt
        history_summary = self._summarize_conversation_history(conv_context.history[-5:])
        
        analysis_prompt = f"""You are an intelligent AI agent that understands user intent and context. 
Analyze the user's input and determine their intent, considering the conversation context.

User Input: "{user_input}"

Recent Conversation History:
{history_summary}

Available System Capabilities:
- Web search and comprehensive information retrieval
- Technical documentation and troubleshooting guides
- Manufacturer support and service information
- Navigation and location services  
- Stock market and financial data
- File system operations
- Image and photo search
- Communication and messaging
- Entertainment recommendations
- Productivity tools
- Learning and education assistance
- Industrial equipment troubleshooting
- Robotic systems support
- Maintenance and repair guidance

Pattern Recognition Result: {pattern_result if pattern_result else "No clear pattern match"}

SPECIAL FOCUS for Technical/Industrial Equipment:
When users ask about equipment problems (like robotic arms, industrial machines, technical devices):
- Prioritize comprehensive troubleshooting information
- Include multiple information sources (manuals, support, forums, videos)
- Provide step-by-step diagnostic procedures
- Include safety considerations
- Suggest professional support contacts
- Look for common issues and solutions
- Include preventive maintenance advice

Your task: Understand what the user wants to accomplish and provide a comprehensive analysis.

Respond with a JSON object containing:
{{
    "intent_category": "one of: navigation, search, information, control, communication, entertainment, productivity, learning, technical_support, unknown",
    "confidence": 0.0-1.0,
    "primary_action": "what the user wants to do",
    "entities": {{"key": "extracted entities"}},
    "context_clues": ["relevant context from conversation"],
    "suggested_tools": ["tools that could help"],
    "execution_steps": [
        {{"step": 1, "action": "first thing to do", "tool": "tool_name"}},
        {{"step": 2, "action": "next thing to do", "tool": "tool_name"}},
        {{"step": 3, "action": "additional comprehensive search", "tool": "tool_name"}}
    ],
    "user_goal": "ultimate goal the user is trying to achieve",
    "requires_clarification": true/false,
    "clarification_questions": ["questions if clarification needed"],
    "information_depth": "basic/detailed/comprehensive",
    "search_keywords": ["additional search terms for comprehensive results"]
}}

Be intelligent and consider:
- Is this a follow-up to previous conversation?
- What tools would be most helpful?
- Are there implicit requests (e.g., "I'm hungry" might mean "find restaurants")?
- Cultural and language context (English/Chinese)
- Time of day and typical user behavior patterns
- For technical issues: What level of detail is needed?
- For equipment problems: What type of comprehensive information should be gathered?

Respond with ONLY the JSON object."""

        try:
            # Get LLM analysis
            response = await llm_manager.generate_response(
                prompt=analysis_prompt,
                model_name="llama3.2",
                temperature=0.3
            )
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis_data = json.loads(json_match.group())
                
                return UserIntent(
                    category=IntentCategory(analysis_data.get("intent_category", "unknown")),
                    action=analysis_data.get("primary_action", "process user request"),
                    entities=analysis_data.get("entities", {}),
                    confidence=analysis_data.get("confidence", 0.5),
                    context={"context_clues": analysis_data.get("context_clues", [])},
                    suggested_tools=analysis_data.get("suggested_tools", []),
                    execution_plan=analysis_data.get("execution_steps", [])
                )
                
        except Exception as e:
            logger.error(f"Error in LLM intent analysis: {e}")
        
        # Fallback intent
        return UserIntent(
            category=IntentCategory.UNKNOWN,
            action="process user request",
            entities={},
            confidence=0.1,
            context={},
            suggested_tools=["web-search"],
            execution_plan=[{"step": 1, "action": "search for information", "tool": "web-search"}]
        )
    
    async def _enhance_with_context(
        self,
        intent: UserIntent,
        conv_context: ConversationContext,
        original_input: str = ""
    ) -> UserIntent:
        """Enhance intent understanding with conversation context"""
        
        # Store original input in context for later use
        if original_input:
            intent.context["original_input"] = original_input
        
        # Check if this follows a previous action
        if conv_context.last_action:
            if intent.category == IntentCategory.UNKNOWN:
                # Try to infer from last action
                if "navigation" in conv_context.last_action:
                    intent.category = IntentCategory.NAVIGATION
                elif "search" in conv_context.last_action:
                    intent.category = IntentCategory.SEARCH
        
        # Enhance confidence based on context clarity
        if len(conv_context.history) > 1:
            intent.confidence = min(1.0, intent.confidence + 0.1)
        
        # Add user preferences if available
        if conv_context.user_preferences:
            intent.context.update(conv_context.user_preferences)
        
        return intent
    
    async def _learn_from_interaction(self, user_input: str, intent: UserIntent):
        """Learn from user interactions to improve future understanding"""
        
        # Store interaction for learning
        interaction_data = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "detected_intent": intent.category.value,
            "action": intent.action,
            "entities": intent.entities,
            "confidence": intent.confidence,
            "tools_used": intent.suggested_tools
        }
        
        self.learning_data.append(interaction_data)
        
        # Store in RAG memory for future reference
        try:
            memory_content = f"""
            User Input Pattern: {user_input}
            Intent: {intent.category.value}
            Action: {intent.action}
            Tools Used: {', '.join(intent.suggested_tools)}
            Confidence: {intent.confidence}
            
            This interaction shows user intent patterns for future reference.
            """
            
            await self.rag_memory.add_document(
                content=memory_content,
                metadata={
                    "type": "interaction_pattern",
                    "intent_category": intent.category.value,
                    "confidence": intent.confidence,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.debug(f"Could not store interaction in memory: {e}")
    
    def _get_conversation_context(self, user_id: str) -> ConversationContext:
        """Get or create conversation context for user"""
        if user_id not in self.conversation_contexts:
            self.conversation_contexts[user_id] = ConversationContext(
                user_id=user_id,
                session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                history=[],
                current_topic=None,
                user_preferences={},
                last_action=None,
                context_embeddings=None
            )
        return self.conversation_contexts[user_id]
    
    def _summarize_conversation_history(self, history: List[Dict]) -> str:
        """Summarize recent conversation history"""
        if not history:
            return "No previous conversation."
        
        summary_lines = []
        for entry in history[-3:]:  # Last 3 entries
            if entry.get("type") == "user":
                summary_lines.append(f"User: {entry.get('user_input', '')}")
            elif entry.get("type") == "agent":
                summary_lines.append(f"Agent: {entry.get('response', '')}")
        
        return "\n".join(summary_lines) if summary_lines else "No previous conversation."
    
    async def execute_intent(self, intent: UserIntent, user_id: str = "default") -> Dict[str, Any]:
        """
        Execute the understood intent using appropriate tools and actions
        """
        
        conv_context = self._get_conversation_context(user_id)
        execution_result = {
            "success": False,
            "action_taken": intent.action,
            "tools_used": [],
            "results": {},
            "response_message": "",
            "follow_up_suggestions": []
        }
        
        try:
            # Execute based on intent category
            if intent.category == IntentCategory.NAVIGATION:
                result = await self._execute_navigation(intent)
            elif intent.category == IntentCategory.SEARCH:
                result = await self._execute_search(intent)
            elif intent.category == IntentCategory.INFORMATION:
                result = await self._execute_information_request(intent)
            elif intent.category == IntentCategory.CONTROL:
                result = await self._execute_control_action(intent)
            elif intent.category == IntentCategory.TECHNICAL_SUPPORT:
                result = await self._execute_technical_support(intent)
            else:
                # Generic execution using suggested tools
                result = await self._execute_generic_action(intent)
            
            execution_result.update(result)
            execution_result["success"] = True
            
            # Update conversation context
            conv_context.last_action = intent.action
            conv_context.history.append({
                "timestamp": datetime.now().isoformat(),
                "type": "agent",
                "intent": intent.category.value,
                "action": intent.action,
                "result": execution_result
            })
            
        except Exception as e:
            logger.error(f"Error executing intent: {e}")
            execution_result["response_message"] = f"I encountered an error while trying to {intent.action}. Let me try a different approach."
        
        return execution_result
    
    async def _execute_navigation(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute navigation-related actions"""
        location = intent.entities.get("entity_0", "")
        if not location:
            # Try to extract from the original input
            original_input = intent.context.get("original_input", "")
            location = self._extract_location(original_input)
        
        # Generate Google Maps URL
        import urllib.parse
        encoded_location = urllib.parse.quote_plus(location)
        maps_url = f"https://www.google.com/maps/search/{encoded_location}"
        
        return {
            "tools_used": ["web-search"],
            "results": {"navigation_target": location, "maps_url": maps_url},
            "response_message": maps_url,
            "rabbitmq_command": {
                "action": "navigate_to",
                "target": location,
                "data": maps_url
            }
        }
    
    def _extract_location(self, original_input: str) -> str:
        """Extract location from original input"""
        # Remove common navigation phrases
        nav_phrases = ['我要去', '帶我去', '導航到', '去', 'go to', 'take me to', 'navigate to', 'I want to go to']
        clean_location = original_input
        for phrase in nav_phrases:
            clean_location = clean_location.replace(phrase, '').strip()
        
        # If still empty, use the original
        if not clean_location or len(clean_location) < 2:
            clean_location = original_input
            
        return clean_location
    
    async def _execute_search(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute search-related actions"""
        # Get the raw entity first
        raw_entity = intent.entities.get("entity_0", "")
        original_input = intent.context.get("original_input", "")
        
        # Always try to extract a cleaner search term, even if we have an entity
        if raw_entity:
            # If we have an entity, use intelligent extraction on it
            logger.info(f"Raw entity from LLM: {raw_entity}")
            search_term = self._extract_search_term(raw_entity)
            logger.info(f"Cleaned search term: {search_term}")
        else:
            # Fallback to extracting from original input
            search_term = self._extract_search_term(original_input)
        
        # Determine if it's an image search or web search
        is_image_search = any(term in intent.action.lower() for term in ['image', 'photo', 'picture', '照片', '圖片', '相片'])
        
        if is_image_search:
            # Generate Google Images search URL
            import urllib.parse
            encoded_term = urllib.parse.quote_plus(search_term)
            image_search_url = f"https://www.google.com/search?q={encoded_term}&tbm=isch"
            
            return {
                "tools_used": ["web-search"],
                "results": {"search_term": search_term, "type": "image", "search_url": image_search_url},
                "response_message": image_search_url,
                "rabbitmq_command": {
                    "action": "search_images",
                    "target": search_term,
                    "data": image_search_url
                }
            }
        else:
            # Generate Google web search URL
            import urllib.parse
            encoded_term = urllib.parse.quote_plus(search_term)
            web_search_url = f"https://www.google.com/search?q={encoded_term}"
            
            return {
                "tools_used": ["web-search"],
                "results": {"search_term": search_term, "type": "web", "search_url": web_search_url},
                "response_message": web_search_url,
                "rabbitmq_command": {
                    "action": "search_web",
                    "target": search_term,
                    "data": web_search_url
                }
            }
    
    def _extract_search_term(self, original_input: str) -> str:
        """Extract search term from original input using intelligent analysis"""
        import re
        
        # First, try simple pattern matching for common formats
        patterns = [
            # Chinese patterns
            r'(?:幫我找|找|搜尋|我要看)?(.+?)(?:的照片|的圖片|的相片|的圖|給我)',
            r'(.+?)(?:圖片|照片|相片|圖)',
            # English patterns  
            r'(?:find|search|show me|get)?(.+?)(?:images?|photos?|pictures?)',
            r'(?:images?|photos?|pictures?) of (.+)',
            # Generic extraction - take the main subject
            r'(?:找|搜尋|search|find)\s*(.+?)(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, original_input, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                if extracted and len(extracted) > 1 and extracted not in ['我', 'me', 'the', '的']:
                    return extracted
        
        # If patterns fail, use AI-powered extraction
        return self._ai_extract_search_term(original_input)
    
    def _ai_extract_search_term(self, original_input: str) -> str:
        """Use AI to extract the main subject from search requests"""
        try:
            # Simple rule-based extraction for now (can be enhanced with LLM)
            text = original_input.lower()
            
            # Remove common Chinese phrases
            chinese_stopwords = ['幫我找', '找', '搜尋', '的照片', '的圖片', '的相片', '給我', '我要', '請給我']
            clean_text = original_input
            for stopword in chinese_stopwords:
                clean_text = clean_text.replace(stopword, ' ')
            
            # Remove common English phrases
            english_stopwords = ['find', 'search', 'show me', 'get', 'images', 'photos', 'pictures', 'of', 'for me']
            for stopword in english_stopwords:
                clean_text = re.sub(rf'\b{stopword}\b', ' ', clean_text, flags=re.IGNORECASE)
            
            # Clean up and extract meaningful words
            clean_text = re.sub(r'[^\w\s]', ' ', clean_text)  # Remove punctuation
            words = [word.strip() for word in clean_text.split() if len(word.strip()) > 1]
            
            # Filter out remaining stopwords and get the main subject
            meaningful_words = [word for word in words if word.lower() not in ['的', 'me', 'the', 'a', 'an']]
            
            if meaningful_words:
                # Return the first meaningful word (usually the subject)
                return meaningful_words[0]
            else:
                # Fallback to original input
                return original_input
                
        except Exception as e:
            logger.warning(f"AI extraction failed: {e}")
            return original_input
    
    async def _execute_information_request(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute information retrieval actions"""
        query = intent.entities.get("entity_0", "")
        
        # Check if it's a stock price request
        if "stock" in intent.action.lower() or "price" in intent.action.lower():
            return {
                "tools_used": ["stock-checker"],
                "results": {"stock_symbol": query},
                "response_message": f"Getting stock information for {query}.",
                "rabbitmq_command": {
                    "action": "get_stock",
                    "target": query,
                    "data": "stock_query"
                }
            }
        else:
            return {
                "tools_used": ["web-search", "rag-memory"],
                "results": {"query": query},
                "response_message": f"Looking up information about {query}.",
                "rabbitmq_command": {
                    "action": "search_web",
                    "target": query,
                    "data": "information_search"
                }
            }
    
    async def _execute_control_action(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute control actions"""
        target = intent.entities.get("entity_0", "")
        
        return {
            "tools_used": ["filesystem"],
            "results": {"control_target": target, "action": intent.action},
            "response_message": f"Executing control action: {intent.action} on {target}.",
            "rabbitmq_command": {
                "action": "control_device",
                "target": target,
                "data": intent.action
            }
        }
    
    async def _execute_generic_action(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute generic actions using suggested tools"""
        return {
            "tools_used": intent.suggested_tools,
            "results": {"action": intent.action, "entities": intent.entities},
            "response_message": f"I'll help you with {intent.action}.",
            "rabbitmq_command": {
                "action": "generic_action",
                "target": str(intent.entities),
                "data": intent.action
            }
        }
    
    async def _execute_technical_support(self, intent: UserIntent) -> Dict[str, Any]:
        """Execute technical support by actually searching for specific equipment information"""
        equipment = intent.entities.get("entity_0", "equipment")
        original_query = intent.context.get("original_input", equipment)
        
        logger.info(f"Technical support request for: {equipment}")
        
        # Determine if this is a usage/manual request vs troubleshooting
        is_usage_request = any(keyword in original_query.lower() for keyword in 
                             ['怎麼使用', '如何使用', 'how to use', '使用方法', '操作手冊', 'manual', '說明'])
        
        try:
            if is_usage_request:
                # Search for usage/manual information
                search_results = await self._search_equipment_manual(equipment, original_query)
                response_data = f"UR10 機械手臂使用說明:\n\n{search_results}"
            else:
                # Search for troubleshooting information
                search_results = await self._search_equipment_troubleshooting(equipment, original_query)
                response_data = f"{equipment} 故障排除資訊:\n\n{search_results}"
            
            return {
                "tools_used": ["web-search", "rag-memory"],
                "results": {
                    "equipment": equipment,
                    "search_results": search_results,
                    "request_type": "usage_manual" if is_usage_request else "troubleshooting"
                },
                "response_message": response_data,
                "rabbitmq_command": {
                    "action": "technical_support_info",
                    "target": equipment,
                    "data": response_data
                }
            }
            
        except Exception as e:
            logger.error(f"Error in technical support search: {e}")
            fallback_message = f"正在為您查找 {equipment} 的相關資訊，請稍候..."
            return {
                "tools_used": ["fallback"],
                "results": {"equipment": equipment, "error": str(e)},
                "response_message": fallback_message,
                "rabbitmq_command": {
                    "action": "technical_support_fallback",
                    "target": equipment,
                    "data": fallback_message
                }
            }
    
    async def _search_equipment_manual(self, equipment: str, original_query: str) -> str:
        """Search for equipment usage manual and instructions"""
        try:
            # Search in RAG memory first
            memory_results = await self.rag_memory.search_similar(f"{equipment} 使用說明 操作手冊", max_results=3)
            
            manual_info = []
            
            if memory_results:
                manual_info.append("=== 已知資訊 ===")
                for result in memory_results:
                    manual_info.append(f"• {result.get('content', '')[:200]}...")
            
            # Generate comprehensive usage guide using LLM
            usage_prompt = f"""
            請提供 {equipment} 的詳細使用說明。包括：
            
            1. 基本操作步驟
            2. 安全注意事項  
            3. 常用功能介紹
            4. 維護保養要點
            5. 常見問題解決
            
            請用繁體中文回答，內容要實用且詳細。
            """
            
            from llm_manager import llm_manager
            usage_guide = await llm_manager.generate_response(
                prompt=usage_prompt,
                model_name="llama3.2",
                temperature=0.3
            )
            
            manual_info.append("\n=== 使用說明 ===")
            manual_info.append(usage_guide)
            
            return "\n".join(manual_info)
            
        except Exception as e:
            logger.error(f"Error searching manual: {e}")
            return f"正在查找 {equipment} 使用說明，請稍候系統處理..."
    
    async def _search_equipment_troubleshooting(self, equipment: str, original_query: str) -> str:
        """Search for equipment troubleshooting information"""
        try:
            # Search in RAG memory for troubleshooting info
            memory_results = await self.rag_memory.search_similar(f"{equipment} 故障 維修 問題", max_results=3)
            
            troubleshoot_info = []
            
            if memory_results:
                troubleshoot_info.append("=== 故障排除資訊 ===")
                for result in memory_results:
                    troubleshoot_info.append(f"• {result.get('content', '')[:200]}...")
            
            # Generate troubleshooting guide
            troubleshoot_prompt = f"""
            {equipment} 出現問題，請提供故障排除指南：
            
            1. 常見故障現象及原因
            2. 診斷步驟
            3. 解決方法
            4. 預防措施
            5. 何時需要專業維修
            
            請用繁體中文回答，提供實用的解決方案。
            """
            
            from llm_manager import llm_manager
            troubleshoot_guide = await llm_manager.generate_response(
                prompt=troubleshoot_prompt,
                model_name="llama3.2", 
                temperature=0.3
            )
            
            troubleshoot_info.append("\n=== 故障排除指南 ===")
            troubleshoot_info.append(troubleshoot_guide)
            
            return "\n".join(troubleshoot_info)
            
        except Exception as e:
            logger.error(f"Error searching troubleshooting: {e}")
            return f"正在查找 {equipment} 故障排除資訊，請稍候..."
    
    def _create_fallback_autonomous_plan(self, equipment: str) -> Dict[str, Any]:
        """Create a fallback autonomous plan when LLM analysis fails"""
        equipment_upper = equipment.upper()
        
        # Smart equipment detection
        if "UR" in equipment_upper and any(char.isdigit() for char in equipment_upper):
            equipment_type = "Collaborative Robot (Universal Robots)"
            manufacturer = "Universal Robots"
            common_issues = ["protective stop", "joint errors", "communication timeout", "calibration drift"]
        elif "ROBOT" in equipment_upper or "ARM" in equipment_upper:
            equipment_type = "Robotic System"
            manufacturer = "Unknown - need to identify"
            common_issues = ["motor failure", "sensor errors", "controller issues", "mechanical binding"]
        else:
            equipment_type = "Industrial Equipment"
            manufacturer = "Unknown - need to identify"
            common_issues = ["power issues", "mechanical failure", "control system error", "sensor malfunction"]
        
        return {
            "equipment_analysis": {
                "equipment_type": equipment_type,
                "manufacturer": manufacturer,
                "common_applications": ["Industrial automation", "Manufacturing", "Assembly"],
                "typical_issues": common_issues
            },
            "autonomous_search_plan": [
                f"{equipment} official manual troubleshooting guide",
                f"{equipment} error codes diagnostic procedures",
                f"{equipment} safety shutdown recovery procedures",
                f"{equipment} manufacturer technical support contact",
                f"{equipment} common problems solutions forum",
                f"{equipment} maintenance service manual",
                f"{equipment} replacement parts suppliers",
                f"{equipment} certified repair technicians",
                f"{equipment} software configuration guides",
                f"{equipment} preventive maintenance schedule"
            ],
            "immediate_diagnostic_steps": [
                "Ensure immediate safety - stop all operations",
                "Activate emergency stop and lockout power",
                "Document all error messages and symptoms",
                "Perform visual inspection for obvious damage",
                "Check power supply and connections",
                "Review system logs and status indicators"
            ],
            "information_priorities": [
                "Safety procedures and emergency stops",
                "Error code meanings and solutions",
                "Step-by-step diagnostic procedures",
                "Manufacturer contact information",
                "Repair procedures and part numbers"
            ],
            "predicted_solutions": [
                "Check and reset safety systems",
                "Verify all electrical connections",
                "Restart system following proper procedure",
                "Contact manufacturer technical support",
                "Schedule professional service inspection"
            ],
            "safety_analysis": {
                "risk_level": "medium",
                "immediate_safety_actions": [
                    "Stop all operations immediately",
                    "Ensure emergency stop is activated",
                    "Prevent unauthorized access to equipment"
                ],
                "ongoing_safety_considerations": [
                    "Follow lockout/tagout procedures",
                    "Use proper PPE during inspection",
                    "Never bypass safety systems"
                ]
            }
        }
    
    async def _execute_autonomous_plan(self, equipment: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the autonomous support plan"""
        
        # Simulate comprehensive information gathering
        # In a real implementation, this would use actual search APIs and databases
        
        comprehensive_data = {
            "equipment_identification": {
                "confirmed_type": plan["equipment_analysis"]["equipment_type"],
                "manufacturer": plan["equipment_analysis"]["manufacturer"],
                "model_details": f"Automatically identified as {equipment}",
                "specifications": "Gathering detailed specifications..."
            },
            "diagnostic_procedures": {
                "immediate_steps": plan["immediate_diagnostic_steps"],
                "detailed_diagnostics": self._generate_detailed_diagnostics(equipment, plan),
                "troubleshooting_flowchart": self._generate_troubleshooting_flowchart(equipment, plan)
            },
            "solutions_database": {
                "predicted_solutions": plan["predicted_solutions"],
                "common_fixes": self._generate_common_fixes(equipment, plan),
                "escalation_procedures": self._generate_escalation_procedures(equipment, plan)
            },
            "safety_information": {
                "risk_assessment": plan["safety_analysis"],
                "safety_procedures": self._generate_safety_procedures(equipment, plan),
                "emergency_contacts": self._generate_emergency_contacts(equipment, plan)
            },
            "support_resources": {
                "documentation_links": self._generate_documentation_links(equipment, plan),
                "video_tutorials": self._generate_video_tutorials(equipment, plan),
                "expert_contacts": self._generate_expert_contacts(equipment, plan)
            },
            "maintenance_guidance": {
                "preventive_maintenance": self._generate_maintenance_schedule(equipment, plan),
                "parts_information": self._generate_parts_info(equipment, plan),
                "service_recommendations": self._generate_service_recommendations(equipment, plan)
            }
        }
        
        return comprehensive_data
    
    def _generate_detailed_diagnostics(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate detailed diagnostic procedures"""
        return [
            {
                "category": "Power System Analysis",
                "procedures": [
                    "Measure input voltage and verify within specifications",
                    "Check all circuit breakers and fuses for continuity",
                    "Test ground connections and verify proper grounding",
                    "Monitor power consumption during operation"
                ],
                "tools_needed": ["Multimeter", "Power analyzer", "Ground tester"],
                "estimated_time": "15-30 minutes"
            },
            {
                "category": "Communication Diagnostics",
                "procedures": [
                    "Test network connectivity and IP configuration",
                    "Verify cable integrity with cable tester",
                    "Check communication protocols and handshaking",
                    "Monitor data transmission rates and errors"
                ],
                "tools_needed": ["Network tester", "Cable analyzer", "Protocol analyzer"],
                "estimated_time": "20-45 minutes"
            },
            {
                "category": "Mechanical System Check",
                "procedures": [
                    "Inspect all moving parts for wear and binding",
                    "Check alignment and calibration accuracy",
                    "Test range of motion and movement smoothness",
                    "Verify mounting stability and vibration levels"
                ],
                "tools_needed": ["Inspection tools", "Calibration gauges", "Vibration meter"],
                "estimated_time": "30-60 minutes"
            }
        ]
    
    def _generate_troubleshooting_flowchart(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate a troubleshooting flowchart"""
        return [
            {
                "decision_point": "Is the equipment powered on?",
                "yes_action": "Proceed to communication check",
                "no_action": "Check power supply and connections",
                "next_step": 2
            },
            {
                "decision_point": "Are there any error messages displayed?",
                "yes_action": "Document error codes and consult manual",
                "no_action": "Proceed to functional testing",
                "next_step": 3
            },
            {
                "decision_point": "Do basic functions work correctly?",
                "yes_action": "Check advanced functionality",
                "no_action": "Isolate the failing subsystem",
                "next_step": 4
            },
            {
                "decision_point": "Is the issue intermittent?",
                "yes_action": "Monitor for pattern and environmental factors",
                "no_action": "Implement permanent fix or contact support",
                "next_step": "resolution"
            }
        ]
    
    def _generate_common_fixes(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate common fixes for the equipment"""
        return [
            {
                "issue": "System not responding",
                "solution": "Power cycle the system",
                "steps": [
                    "Ensure safe shutdown procedure",
                    "Wait 30 seconds after power off",
                    "Restore power and monitor startup",
                    "Verify all systems come online properly"
                ],
                "success_rate": "85%"
            },
            {
                "issue": "Communication errors",
                "solution": "Reset communication interfaces",
                "steps": [
                    "Check cable connections",
                    "Reset network settings to default",
                    "Reconfigure communication parameters",
                    "Test communication with simple commands"
                ],
                "success_rate": "70%"
            },
            {
                "issue": "Calibration drift",
                "solution": "Recalibrate system",
                "steps": [
                    "Access calibration menu",
                    "Follow manufacturer's calibration procedure",
                    "Verify calibration with test movements",
                    "Save calibration parameters"
                ],
                "success_rate": "90%"
            }
        ]
    
    def _generate_escalation_procedures(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate escalation procedures"""
        return [
            {
                "level": "Level 1 - Internal Support",
                "when_to_use": "Basic troubleshooting unsuccessful",
                "contacts": ["Local maintenance team", "Operations supervisor"],
                "timeline": "Immediate"
            },
            {
                "level": "Level 2 - Vendor Support",
                "when_to_use": "Internal support cannot resolve",
                "contacts": ["Manufacturer technical support", "Local distributor"],
                "timeline": "Within 24 hours"
            },
            {
                "level": "Level 3 - Expert Support",
                "when_to_use": "Complex or critical issues",
                "contacts": ["Field service engineer", "Applications specialist"],
                "timeline": "Within 48-72 hours"
            }
        ]
    
    def _generate_safety_procedures(self, equipment: str, plan: Dict) -> List[str]:
        """Generate comprehensive safety procedures"""
        return [
            "🛑 IMMEDIATE: Activate emergency stop and lockout power",
            "🔒 Implement lockout/tagout procedures per company policy",
            "👥 Notify all personnel in the work area of the issue",
            "📋 Document the failure mode and any safety implications",
            "🦺 Ensure proper PPE is worn during all diagnostic work",
            "⚠️ Never bypass or disable safety systems",
            "🔍 Inspect for any physical hazards before beginning work",
            "📞 Contact safety personnel if unsure about any procedure"
        ]
    
    def _generate_emergency_contacts(self, equipment: str, plan: Dict) -> Dict[str, str]:
        """Generate emergency contact information"""
        return {
            "immediate_safety": "Emergency Services: 911",
            "company_safety": "Internal Safety Hotline: [Company specific]",
            "equipment_emergency": f"{equipment} Emergency Support: [Manufacturer specific]",
            "maintenance_emergency": "After-hours Maintenance: [Company specific]",
            "management_notification": "Operations Manager: [Company specific]"
        }
    
    def _generate_documentation_links(self, equipment: str, plan: Dict) -> List[str]:
        """Generate documentation links"""
        return [
            f"Official {equipment} User Manual",
            f"{equipment} Service and Maintenance Guide",
            f"{equipment} Troubleshooting Quick Reference",
            f"{equipment} Safety and Installation Manual",
            f"{equipment} Software Configuration Guide",
            f"{equipment} Parts Catalog and Ordering Information"
        ]
    
    def _generate_video_tutorials(self, equipment: str, plan: Dict) -> List[str]:
        """Generate video tutorial recommendations"""
        return [
            f"{equipment} Basic Operation and Safety",
            f"{equipment} Troubleshooting Common Issues",
            f"{equipment} Maintenance and Calibration Procedures",
            f"{equipment} Emergency Stop and Recovery Procedures",
            f"{equipment} Advanced Configuration and Setup"
        ]
    
    def _generate_expert_contacts(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate expert contact information"""
        return [
            {
                "type": "Manufacturer Technical Support",
                "description": f"Official {equipment} technical support team",
                "contact_method": "Phone, Email, Online Chat"
            },
            {
                "type": "Certified Service Technicians",
                "description": f"Local certified {equipment} service providers",
                "contact_method": "Service request portal"
            },
            {
                "type": "User Community Forums",
                "description": f"{equipment} user community and expert discussions",
                "contact_method": "Online forums and communities"
            }
        ]
    
    def _generate_maintenance_schedule(self, equipment: str, plan: Dict) -> Dict[str, List]:
        """Generate maintenance schedule"""
        return {
            "daily": [
                "Visual inspection for obvious issues",
                "Check error logs and status indicators",
                "Verify safety systems are functional"
            ],
            "weekly": [
                "Clean external surfaces and ventilation",
                "Check cable connections and routing",
                "Test emergency stop functionality"
            ],
            "monthly": [
                "Calibration verification and adjustment",
                "Lubrication per manufacturer specifications",
                "Backup configuration and program files"
            ],
            "quarterly": [
                "Comprehensive system inspection",
                "Software updates and patches",
                "Professional service technician review"
            ],
            "annually": [
                "Complete system overhaul and certification",
                "Replace wear items per schedule",
                "Update safety systems and documentation"
            ]
        }
    
    def _generate_parts_info(self, equipment: str, plan: Dict) -> Dict[str, Any]:
        """Generate parts information"""
        return {
            "common_replacement_parts": [
                "Cables and connectors",
                "Filters and seals",
                "Sensors and switches",
                "Motors and actuators"
            ],
            "recommended_spare_parts": [
                "Critical wear items",
                "Emergency replacement components",
                "Consumable items"
            ],
            "part_ordering_info": {
                "supplier": f"Official {equipment} parts supplier",
                "lead_times": "Standard: 1-2 weeks, Critical: 24-48 hours",
                "warranty": "Parts warranty information"
            }
        }
    
    def _generate_service_recommendations(self, equipment: str, plan: Dict) -> List[Dict]:
        """Generate service recommendations"""
        return [
            {
                "recommendation": "Immediate Service Required",
                "when": "Safety systems compromised or critical failures",
                "urgency": "Emergency",
                "action": "Contact certified technician immediately"
            },
            {
                "recommendation": "Scheduled Service",
                "when": "Performance degradation or minor issues",
                "urgency": "Within 1 week",
                "action": "Schedule service appointment"
            },
            {
                "recommendation": "Preventive Service",
                "when": "Routine maintenance intervals",
                "urgency": "As scheduled",
                "action": "Follow maintenance schedule"
            }
        ]

# Global intelligent agent instance
intelligent_agent = IntelligentAgent()
