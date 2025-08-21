import logging
from typing import Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from sqlalchemy.orm import Session

from src.data.models import User, UserInteraction, PersonalizationProfile
from config.database import db_manager
from config.settings import settings

logger = logging.getLogger(__name__)

class StudyHelperBot:
    """Main bot class encapsulating all bot functionality"""
    
    def __init__(self):
        self.application = None
        self._setup_application()
    
    def _setup_application(self):
        """Initialize the bot application"""
        self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        self._add_handlers()
        logger.info("Telegram bot application initialized")
    
    def _add_handlers(self):
        """Add all command and message handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("courses", self.courses_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_query))
        
        # Callback query handlers (for inline keyboards)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_data = update.effective_user
        
        try:
            # Get or create user in database
            with db_manager.get_session() as session:
                user = self._get_or_create_user(session, user_data)
                
                # Create welcome message
                welcome_text = f"""
🎓 Welcome to Study Helper Agent, {user.first_name}!

I'm your AI-powered academic assistant. I can help you with:
• 📚 Answering questions about your course materials
• 📋 Tracking assignments and deadlines  
• 🔔 Getting notified about new content
• 📈 Personalizing your learning experience

To get started:
1. Use /courses to see available courses
2. Ask me questions about your studies
3. Use /help for more commands

Example: "What are the main topics in today's lecture notes?"
                """.strip()
                
                # Create inline keyboard for quick actions
                keyboard = [
                    [
                        InlineKeyboardButton("📚 View Courses", callback_data="view_courses"),
                        InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                    ],
                    [
                        InlineKeyboardButton("❓ Help", callback_data="help"),
                        InlineKeyboardButton("👤 Profile", callback_data="profile")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(welcome_text, reply_markup=reply_markup)
                
                # Log interaction
                self._log_interaction(
                    session, user.id, "/start", welcome_text, "command"
                )
                
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error. Please try again later."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🆘 **Study Helper Agent Commands**

**Basic Commands:**
/start - Initialize the bot and see welcome message
/help - Show this help message
/profile - View your learning profile
/courses - View enrolled courses
/settings - Adjust your preferences

**How to Use:**
📝 **Ask Questions**: Just type your question naturally
   Example: "Explain the concept of inheritance in OOP"

🔍 **Search Content**: Ask about specific topics
   Example: "What did the professor say about databases?"

📊 **Get Summaries**: Request summaries of materials
   Example: "Summarize today's lecture on algorithms"

**Tips for Better Results:**
• Be specific about which course or topic
• Ask follow-up questions for clarification
• Rate my responses to improve personalization
• Use /settings to customize your experience

Need more help? Just ask me anything!
        """.strip()
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command"""
        user_data = update.effective_user
        
        try:
            with db_manager.get_session() as session:
                user = session.query(User).filter(User.telegram_id == str(user_data.id)).first()
                
                if not user:
                    await update.message.reply_text("Please use /start first to initialize your profile.")
                    return
                
                # Get personalization profile
                profile = session.query(PersonalizationProfile).filter(
                    PersonalizationProfile.user_id == user.id
                ).first()
                
                # Calculate some basic stats
                total_interactions = session.query(UserInteraction).filter(
                    UserInteraction.user_id == user.id
                ).count()
                
                profile_text = f"""
👤 **Your Learning Profile**

**Basic Info:**
• Name: {user.first_name} {user.last_name or ''}
• Learning Style: {user.learning_style.title()}
• Preferred Difficulty: {user.difficulty_preference.title()}

**Activity Stats:**
• Total Interactions: {total_interactions}
• Member Since: {user.created_at.strftime('%B %Y')}
• Last Active: {user.updated_at.strftime('%B %d, %Y')}

**Personalization:**
• Status: {'Active' if profile and profile.total_interactions >= settings.MIN_INTERACTIONS_FOR_PERSONALIZATION else 'Learning your preferences...'}
• Avg Session: {profile.avg_session_duration if profile else 0:.1f} minutes

Use /settings to customize your preferences!
                """.strip()
                
                await update.message.reply_text(profile_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Error in profile_command: {e}")
            await update.message.reply_text("Sorry, couldn't retrieve your profile. Please try again.")
    
    async def courses_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /courses command"""
        # For now, show mock courses since we haven't implemented LMS integration yet
        courses_text = """
📚 **Your Enrolled Courses**

*Currently showing mock data - LMS integration coming soon!*

🖥️ **ICS 201 - Data Structures**
   • Status: Active
   • New materials: 2 documents

💻 **ICS 301 - Software Engineering** 
   • Status: Active  
   • New materials: 1 assignment

🧮 **MAT 201 - Discrete Mathematics**
   • Status: Active
   • New materials: 3 lecture notes

To ask course-specific questions, mention the course:
"What are stacks in ICS 201?"
        """.strip()
        
        keyboard = [
            [InlineKeyboardButton("🔔 Enable Notifications", callback_data="enable_notifications")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(courses_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        keyboard = [
            [
                InlineKeyboardButton("📖 Learning Style", callback_data="setting_learning_style"),
                InlineKeyboardButton("📊 Difficulty", callback_data="setting_difficulty")
            ],
            [
                InlineKeyboardButton("🔔 Notifications", callback_data="setting_notifications"),
                InlineKeyboardButton("📱 Response Length", callback_data="setting_response_length")
            ],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        settings_text = """
⚙️ **Settings & Preferences**

Customize your Study Helper Agent experience:

• **Learning Style**: How you prefer to learn (visual, auditory, etc.)
• **Difficulty Level**: Complexity of explanations you prefer  
• **Notifications**: When to receive updates about new content
• **Response Length**: How detailed you want my responses

Choose a setting to modify:
        """.strip()
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text queries - main AI interaction"""
        user_data = update.effective_user
        query_text = update.message.text
        
        try:
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            with db_manager.get_session() as session:
                user = self._get_or_create_user(session, user_data)
                
                # For now, provide a simple response since we haven't implemented RAG yet
                # This will be replaced with actual AI processing later
                response_text = await self._process_query_basic(query_text, user)
                
                # Send response
                await update.message.reply_text(response_text, parse_mode='Markdown')
                
                # Create feedback buttons
                keyboard = [
                    [
                        InlineKeyboardButton("👍 Helpful", callback_data=f"feedback_helpful_{len(query_text)}"),
                        InlineKeyboardButton("👎 Not helpful", callback_data=f"feedback_unhelpful_{len(query_text)}"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Was this response helpful?", 
                    reply_markup=reply_markup
                )
                
                # Log interaction
                self._log_interaction(
                    session, user.id, query_text, response_text, "question"
                )
                
        except Exception as e:
            logger.error(f"Error in handle_query: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error processing your question. Please try again."
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()  # Acknowledge the callback
        
        callback_data = query.data
        
        try:
            if callback_data == "view_courses":
                await self.courses_command(update, context)
            
            elif callback_data == "settings":
                await self.settings_command(update, context)
            
            elif callback_data == "help":
                await self.help_command(update, context)
            
            elif callback_data == "profile":
                await self.profile_command(update, context)
            
            elif callback_data.startswith("feedback_"):
                await self._handle_feedback(update, context, callback_data)
            
            elif callback_data.startswith("setting_"):
                await self._handle_setting_change(update, context, callback_data)
            
            elif callback_data == "enable_notifications":
                await query.edit_message_text(
                    "🔔 Notifications enabled! I'll notify you when new course materials are available.",
                    parse_mode='Markdown'
                )
            
            else:
                await query.edit_message_text("Feature coming soon!")
                
        except Exception as e:
            logger.error(f"Error in handle_callback: {e}")
            await query.edit_message_text("Sorry, something went wrong. Please try again.")
    
    async def _process_query_basic(self, query: str, user: User) -> str:
        """Basic query processing - will be replaced with RAG pipeline later"""
        query_lower = query.lower()
        
        # Simple keyword-based responses for testing
        if any(word in query_lower for word in ['hello', 'hi', 'hey']):
            return f"Hello {user.first_name}! How can I help you with your studies today?"
        
        elif any(word in query_lower for word in ['data structure', 'stack', 'queue']):
            return """
📚 **Data Structures Overview**

**Stack (LIFO - Last In, First Out):**
• Elements added/removed from the top
• Main operations: push(), pop(), peek()
• Use cases: Function calls, expression evaluation

**Queue (FIFO - First In, First Out):**  
• Elements added at rear, removed from front
• Main operations: enqueue(), dequeue(), front()
• Use cases: Task scheduling, breadth-first search

*Note: This is a basic response. Full AI-powered responses coming soon!*
            """.strip()
        
        elif any(word in query_lower for word in ['algorithm', 'sort', 'search']):
            return """
🔍 **Algorithms Basics**

**Common Sorting Algorithms:**
• Bubble Sort: O(n²) - Simple but inefficient
• Quick Sort: O(n log n) - Efficient divide-and-conquer
• Merge Sort: O(n log n) - Stable and consistent

**Search Algorithms:**
• Linear Search: O(n) - Sequential checking
• Binary Search: O(log n) - Requires sorted data

*Full course material analysis coming with RAG implementation!*
            """.strip()
        
        elif any(word in query_lower for word in ['assignment', 'deadline', 'due']):
            return """
📋 **Assignment Tracking**

*Currently showing mock data - LMS integration in progress:*

**Upcoming Deadlines:**
• ICS 201: Data Structures Assignment - Due March 15
• ICS 301: Software Design Document - Due March 20  
• MAT 201: Problem Set 3 - Due March 18

I'll soon be able to automatically track real assignments from your LMS!
            """.strip()
        
        else:
            return f"""
I understand you're asking about: "{query}"

🚧 **AI Processing Coming Soon!**

I'm currently in development mode. Soon I'll be able to:
• Search through your actual course materials
• Provide detailed, contextual answers
• Reference specific lecture notes and textbooks
• Adapt responses to your learning style

For now, try asking about:
• Data structures (stack, queue)
• Algorithms (sorting, searching)  
• Assignments and deadlines

Use /help for available commands!
            """
    
    async def _handle_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle user feedback on responses"""
        query = update.callback_query
        
        # Parse feedback
        is_helpful = "helpful" in callback_data and "unhelpful" not in callback_data
        
        try:
            user_data = update.effective_user
            with db_manager.get_session() as session:
                # Find the most recent interaction for this user
                user = session.query(User).filter(User.telegram_id == str(user_data.id)).first()
                if user:
                    recent_interaction = session.query(UserInteraction).filter(
                        UserInteraction.user_id == user.id
                    ).order_by(UserInteraction.created_at.desc()).first()
                    
                    if recent_interaction:
                        recent_interaction.was_helpful = is_helpful
                        recent_interaction.user_rating = 5 if is_helpful else 2
                        session.commit()
            
            feedback_text = "👍 Thanks for the feedback! This helps me learn." if is_helpful else "👎 Thanks for the feedback. I'll work on improving my responses."
            await query.edit_message_text(feedback_text)
            
        except Exception as e:
            logger.error(f"Error handling feedback: {e}")
            await query.edit_message_text("Thanks for the feedback!")
    
    async def _handle_setting_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Handle settings changes"""
        query = update.callback_query
        setting_type = callback_data.replace("setting_", "")
        
        if setting_type == "learning_style":
            keyboard = [
                [
                    InlineKeyboardButton("👁️ Visual", callback_data="set_visual"),
                    InlineKeyboardButton("👂 Auditory", callback_data="set_auditory")
                ],
                [
                    InlineKeyboardButton("✋ Kinesthetic", callback_data="set_kinesthetic"),
                    InlineKeyboardButton("🧠 Adaptive", callback_data="set_adaptive")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📖 **Choose Your Learning Style:**\n\n"
                "• **Visual**: Learn better with diagrams and visual aids\n"
                "• **Auditory**: Prefer verbal explanations\n" 
                "• **Kinesthetic**: Learn by doing and examples\n"
                "• **Adaptive**: Let me adapt to your preferences automatically",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        elif setting_type == "difficulty":
            keyboard = [
                [
                    InlineKeyboardButton("😊 Easy", callback_data="set_easy"),
                    InlineKeyboardButton("😐 Medium", callback_data="set_medium"),
                    InlineKeyboardButton("😅 Hard", callback_data="set_hard")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📊 **Choose Difficulty Level:**\n\n"
                "• **Easy**: Simple explanations with basic examples\n"
                "• **Medium**: Balanced detail with practical examples\n"
                "• **Hard**: Comprehensive explanations with advanced concepts",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        else:
            await query.edit_message_text("Setting configuration coming soon!")
    
    def _get_or_create_user(self, session: Session, user_data) -> User:
        """Get existing user or create new one"""
        user = session.query(User).filter(User.telegram_id == str(user_data.id)).first()
        
        if not user:
            # Create new user
            user = User(
                telegram_id=str(user_data.id),
                username=user_data.username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                learning_style="adaptive",
                difficulty_preference="medium"
            )
            session.add(user)
            session.flush()  # Get the user ID
            
            # Create personalization profile
            profile = PersonalizationProfile(
                user_id=user.id,
                total_interactions=0,
                successful_interactions=0,
                avg_session_duration=0.0
            )
            session.add(profile)
            session.commit()
            
            logger.info(f"Created new user: {user_data.first_name} ({user_data.id})")
        
        return user
    
    def _log_interaction(self, session: Session, user_id: int, query: str, response: str, interaction_type: str):
        """Log user interaction for analytics and personalization"""
        interaction = UserInteraction(
            user_id=user_id,
            query_text=query,
            response_text=response,
            interaction_type=interaction_type,
            response_time_ms=0  # Will be calculated properly later
        )
        session.add(interaction)
        
        # Update personalization profile
        profile = session.query(PersonalizationProfile).filter(
            PersonalizationProfile.user_id == user_id
        ).first()
        
        if profile:
            profile.total_interactions += 1
            profile.last_interaction = datetime.now()
        
        session.commit()
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update.message:
            await update.message.reply_text(
                "Sorry, I encountered an unexpected error. Please try again or use /help for assistance."
            )
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Study Helper Agent bot...")
        self.application.run_polling()
    
    def stop(self):
        """Stop the bot"""
        if self.application:
            self.application.stop()
            logger.info("Bot stopped")