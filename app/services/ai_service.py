"""
AI Service for OpenAI integration
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.database import supabase
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import logger


class AIService:
    """Service for AI operations using OpenAI (ASYNC)"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def analyze_post_image(
        self,
        image_url: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a post image and extract insights
        
        Args:
            image_url: URL of the image to analyze
            caption: Optional caption text
            
        Returns:
            Dictionary containing insights
        """
        try:
            cleaned_url = image_url.strip()
            
            if '?' in cleaned_url:
                cleaned_url = cleaned_url.split('?')[0] + '?' + cleaned_url.split('?')[1].strip()
            
            prompt = self._build_post_analysis_prompt(caption)
            
            vision_model = "gpt-4o" if "gpt-4o" in self.model else "gpt-4-turbo"
            
            response = await self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing social media posts and extracting detailed insights."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": cleaned_url,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                    result = json.loads(json_str)
                else:
                    result = {
                        "summary": content,
                        "location_guess": None,
                        "outfit_items": [],
                        "objects": [],
                        "vibe_descriptors": [],
                        "colors": [],
                        "activities": [],
                        "interests": [],
                        "confidence_score": 0.5
                    }
            
            logger.info(f"Successfully analyzed post image: {cleaned_url[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing post image: {str(e)}")
            raise
    
    async def analyze_post_text(
        self,
        caption: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze post caption/text to extract insights
        
        Args:
            caption: Post caption text
            metadata: Additional metadata
            
        Returns:
            Dictionary containing insights
        """
        try:
            prompt = self._build_text_analysis_prompt(caption, metadata)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing social media content and extracting meaningful insights."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info("Successfully analyzed post text")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing post text: {str(e)}")
            raise
    
    async def process_network_query(
        self,
        query: str,
        user_signals: List[Dict[str, Any]],
        connection_degree: int
    ) -> Dict[str, Any]:
        """
        Process natural language network query to extract search criteria
        
        Args:
            query: Natural language query
            user_signals: List of user signals/attributes
            connection_degree: Max degree to search
            
        Returns:
            Structured search criteria
        """
        try:
            prompt = self._build_network_query_prompt(query, user_signals, connection_degree)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at parsing social network queries and extracting search criteria."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully processed network query: {query}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing network query: {str(e)}")
            raise
    
    async def generate_chat_response(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        post_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate best-friend style chat response
        
        Args:
            user_message: User's message
            conversation_history: Previous conversation
            post_context: Optional post context
            
        Returns:
            Chat response text
        """
        try:
            system_prompt = self._build_chat_system_prompt()
            messages = [{"role": "system", "content": system_prompt}]
            
            messages.extend(conversation_history[-10:])
            
            current_message = user_message
            if post_context:
                current_message = f"[Post context: {json.dumps(post_context)}]\n\nUser: {user_message}"
            
            messages.append({"role": "user", "content": current_message})
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=300,
                temperature=0.8
            )
            
            reply = response.choices[0].message.content.strip()
            logger.info("Successfully generated chat response")
            return reply
            
        except Exception as e:
            logger.error(f"Error generating chat response: {str(e)}")
            raise
    
    async def generate_persuasion_message(
        self,
        user_id: str,
        ghost_ask_content: str,
        attempt_count: int
    ) -> str:
        """
        Generate persuasive message to encourage posting for ghost ask unlock
        
        Args:
            user_id: User ID
            ghost_ask_content: The ghost ask message
            attempt_count: Number of persuasion attempts
            
        Returns:
            Persuasion message
        """
        try:
            prompt = f"""
            The user wants to send an anonymous "ghost ask" to someone in their network.
            However, they haven't posted within the 6-minute challenge window.
            
            Generate a warm, friendly persuasion message to encourage them to post first.
            This is attempt #{attempt_count}.
            
            - Use lowercase, best-friend tone
            - Be warm but firm
            - Explain why posting first makes the ghost ask more meaningful
            - If attempt > 5, be more understanding but still encouraging
            - If attempt > 10, be very understanding and consider allowing it
            
            Return ONLY the persuasion message text, no JSON.
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are Six, a warm and supportive best friend chatbot."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=200,
                temperature=0.9
            )
            
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated persuasion message for user {user_id}, attempt {attempt_count}")
            return message
            
        except Exception as e:
            logger.error(f"Error generating persuasion message: {str(e)}")
            raise
    
    async def generate_intro_message(
        self,
        requester_name: str,
        target_name: str,
        mutual_count: int,
        query_snippet: str,
        why_match: str
    ) -> str:
        """
        Generate warm intro message for connecting two users
        
        Args:
            requester_name: Name of person requesting intro
            target_name: Name of person being introduced
            mutual_count: Number of mutual connections
            query_snippet: Original query context
            why_match: Why the target matches
            
        Returns:
            Intro message text
        """
        try:
            prompt = f"""
            Generate a warm intro message to connect two people who share {mutual_count} mutual connections.
            
            Context:
            - {requester_name} was asking about: "{query_snippet}"
            - {target_name} fits because: {why_match}
            
            Follow this format (use lowercase, best-friend tone):
            "hey [first name A] & [first name B]! you share [N] mutuals. [A] was asking about '[query]', 
            and [B] fits because [why]. say hi!"
            
            Return ONLY the intro message, no JSON.
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are Six, creating warm introductions between friends."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated intro message for {requester_name} & {target_name}")
            return message
            
        except Exception as e:
            logger.error(f"Error generating intro message: {str(e)}")
            raise
    
    # ==================== Prompt Builders ====================
    
    def _build_post_analysis_prompt(self, caption: Optional[str] = None) -> str:
        """Build prompt for post analysis"""
        base_prompt = """
        Analyze this social media post and extract the following insights.
        
        IMPORTANT: Return ONLY a valid JSON object with this exact structure:
        
        {
            "location_guess": "best guess of location (city/venue) or null",
            "outfit_items": ["list of visible clothing/accessories"],
            "objects": ["list of visible objects, brands, products"],
            "vibe_descriptors": ["mood/vibe words like 'cozy', 'energetic', 'chill'"],
            "colors": ["dominant colors"],
            "activities": ["activities happening in the image"],
            "interests": ["inferred interests based on content"],
            "summary": "brief 1-2 sentence summary",
            "confidence_score": 0.85
        }
        
        Rules:
        - Be specific and observant
        - Extract brand names if visible
        - Use null for unknown fields, not empty strings
        - Return ONLY the JSON object, no markdown code blocks
        - Confidence score should be between 0.0 and 1.0
        """
        
        if caption:
            base_prompt += f"\n\nPost caption: {caption}"
        
        base_prompt += "\n\nReturn the JSON object now:"
        
        return base_prompt
    
    def _build_text_analysis_prompt(
        self,
        caption: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build prompt for text-only analysis"""
        prompt = f"""
        Analyze this social media post caption and extract insights in JSON format:
        
        Caption: {caption}
        """
        
        if metadata:
            prompt += f"\nMetadata: {json.dumps(metadata)}"
        
        prompt += """
        
        Return JSON with:
        {
            "location_guess": "mentioned or inferred location or null",
            "interests": ["inferred interests/topics"],
            "vibe_descriptors": ["mood/tone descriptors"],
            "activities": ["mentioned activities"],
            "summary": "brief summary",
            "confidence_score": 0.0-1.0
        }
        """
        
        return prompt
    
    def _build_network_query_prompt(
        self,
        query: str,
        user_signals: List[Dict[str, Any]],
        connection_degree: int
    ) -> str:
        """Build prompt for network query processing"""
        return f"""
        Parse this natural language network query and extract search criteria:
        
        Query: "{query}"
        
        Available user signals to search: {json.dumps(user_signals[:5])}  # Sample
        Max connection degree: {connection_degree}
        
        Extract and return JSON with:
        {{
            "location": "city/place mentioned or null",
            "school": "school/university mentioned or null",
            "interests": ["extracted interests/hobbies"],
            "keywords": ["other relevant search keywords"],
            "objects": ["specific items mentioned (like 'red heels')"],
            "activities": ["activities mentioned"],
            "time_context": "time reference if any (like 'this month') or null"
        }}
        
        Be precise and extract ALL relevant criteria.
        """
    
    async def match_user_to_query_semantic(
        self,
        query: str,
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to semantically match a user against a natural language query
        
        Args:
            query: Natural language query
            user_data: User profile and signals data
            
        Returns:
            Dictionary with match_score (0-10), match_reasons, and confidence
        """
        try:
            prompt = f"""
            Determine if this user matches the following search query using semantic understanding:
            
            QUERY: "{query}"
            
            USER DATA:
            - Name: {user_data.get('name', 'Unknown')}
            - School: {user_data.get('school', 'Not specified')}
            - Major: {user_data.get('major', 'Not specified')}
            - Graduation Year: {user_data.get('graduation_year', 'Not specified')}
            - Interests/Keywords: {', '.join(user_data.get('keyword_summary', []) if isinstance(user_data.get('keyword_summary'), list) else []) or 'None'}
            - Recent Posts: {json.dumps(user_data.get('recent_posts', [])[:3])}
            
            INSTRUCTIONS:
            1. Analyze if this user semantically matches the query
            2. Consider:
               - Location mentions (in school, posts, or profile)
               - Interests and hobbies (explicit or inferred from posts)
               - Activities and lifestyle
               - Objects or items they have/mention
               - School and academic info
               - Temporal context (if query mentions time like "this month")
            3. Use semantic understanding - don't just match keywords
               Examples:
               - "coffee lover" matches someone who posts about cafes
               - "into fashion" matches someone with outfit posts
               - "in SF" matches someone at SF State or posting from SF
            
            Return JSON:
            {{
                "is_match": true/false,
                "match_score": 0-10 (0=no match, 10=perfect match),
                "match_reasons": ["reason 1", "reason 2", ...],
                "confidence": 0.0-1.0,
                "relevant_details": ["specific detail from profile that matches"]
            }}
            
            Be generous with matches but accurate with scoring.
            If unclear, err on the side of inclusion with lower score.
            """
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at semantic matching and understanding natural language queries about people."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=400,
                temperature=0.3,  # Lower temperature for consistent matching
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error in semantic matching: {str(e)}")
            # Return default no-match on error
            return {
                "is_match": False,
                "match_score": 0,
                "match_reasons": [],
                "confidence": 0.0,
                "relevant_details": []
            }
    
    async def create_thread(self):
        """
        Create a new OpenAI thread for conversation continuity
        
        Returns:
            OpenAI thread object
        """
        try:
            thread = await self.client.beta.threads.create()
            logger.info(f"Created OpenAI thread: {thread.id}")
            return thread
            
        except Exception as e:
            logger.error(f"Error creating OpenAI thread: {str(e)}")
            raise
    
    async def send_thread_message(
        self,
        thread_id: str,
        message: str,
        original_message: Optional[str] = None
    ) -> str:
        """
        Send message using regular chat completions (simpler approach)
        
        Args:
            thread_id: Thread ID (used for conversation continuity)
            message: User's message (may include context for AI)
            original_message: Original user message without context (for storage)
            
        Returns:
            AI response text
        """
        try:
            conversation_history = await self.get_thread_messages(thread_id)
            
            messages = [
                {
                    "role": "system",
                    "content": self._build_chat_system_prompt()
                }
            ]
            
            for msg in conversation_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            messages.append({
                "role": "user",
                "content": message
            })
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            
            message_to_store = original_message if original_message else message
            logger.info(f"Storing message for thread {thread_id}: original='{original_message}', to_store='{message_to_store[:50]}...'")
            await self._store_conversation_in_thread(thread_id, message_to_store, response_text)
            
            logger.info(f"Got response for thread {thread_id}")
            return response_text
                
        except Exception as e:
            logger.error(f"Error sending thread message: {str(e)}")
            return "sorry, i'm having trouble right now. can you try again?"
    
    async def get_thread_messages(self, thread_id: str) -> list:
        """
        Get conversation history from database
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of messages in format [{"role": "user/assistant", "content": "..."}]
        """
        try:
            
            response = supabase.table("chat_sessions").select(
                "conversation_history"
            ).eq("thread_id", thread_id).single().execute()
            
            if response.data and response.data.get("conversation_history"):
                history = response.data["conversation_history"]
                logger.info(f"Retrieved {len(history)} messages from thread {thread_id}")
                return history
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting thread messages: {str(e)}")
            return []
    
    async def _store_conversation_in_thread(
        self,
        thread_id: str,
        user_message: str,
        ai_response: str
    ) -> None:
        """
        Store conversation in thread history
        
        Args:
            thread_id: Thread ID
            user_message: User's message
            ai_response: AI's response
        """
        try:
            
            response = supabase.table("chat_sessions").select(
                "conversation_history"
            ).eq("thread_id", thread_id).single().execute()
            
            current_history = []
            if response.data and response.data.get("conversation_history"):
                current_history = response.data["conversation_history"]
            
            timestamp = datetime.utcnow().isoformat()
            current_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": timestamp
            })
            current_history.append({
                "role": "assistant",
                "content": ai_response,
                "timestamp": timestamp
            })
            
            supabase.table("chat_sessions").update({
                "conversation_history": current_history
            }).eq("thread_id", thread_id).execute()
            
            logger.info(f"Stored conversation in thread {thread_id} (total messages: {len(current_history)})")
            
        except Exception as e:
            logger.error(f"Error storing conversation: {str(e)}")

    def _build_chat_system_prompt(self) -> str:
        """Build system prompt for chat responses"""
        return """
        You are Six, a warm and supportive best friend chatbot.
        
        Personality:
        - Use lowercase text (like texting a friend)
        - Be warm, casual, and supportive
        - Keep responses brief and conversational
        - Show empathy and understanding
        - Occasionally use light humor
        - Remember context from the conversation
        
        Capabilities:
        - Help analyze posts
        - Answer questions about their network
        - Have friendly conversations
        - Provide emotional support
        
        Keep responses under 50 words unless more detail is needed.
        """


ai_service = AIService()

