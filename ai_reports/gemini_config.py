import google.generativeai as genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

def get_best_available_model():
    """
    Automatically detect and return the best available Gemini model.
    This handles regional differences and API version changes.
    """
    try:
        # List all available models
        all_models = genai.list_models()
        
        # Filter models that support generateContent
        available_models = []
        for m in all_models:
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        logger.info("=" * 60)
        logger.info("🔍 Gemini Model Detection")
        logger.info("=" * 60)
        logger.info(f"Found {len(available_models)} available models:")
        for model in available_models:
            logger.info(f"  ✓ {model}")
        
        # Priority list of models (best to worst for our use case)
        priority_models = [
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash-002',
            'models/gemini-1.5-flash-001',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro-latest',
            'models/gemini-1.5-pro-002',
            'models/gemini-1.5-pro-001',
            'models/gemini-1.5-pro',
            'models/gemini-2.0-flash-exp',
            'models/gemini-pro-latest',
            'models/gemini-pro',
        ]
        
        # Find first available model from priority list
        for model_name in priority_models:
            if model_name in available_models:
                # Remove 'models/' prefix for GenerativeModel
                model_id = model_name.replace('models/', '')
                logger.info("=" * 60)
                logger.info(f"✅ Selected Model: {model_id}")
                logger.info("=" * 60)
                return model_id
        
        # If no priority model found, use first available
        if available_models:
            fallback = available_models[0].replace('models/', '')
            logger.warning("=" * 60)
            logger.warning(f"⚠️  No priority model found. Using fallback: {fallback}")
            logger.warning("=" * 60)
            return fallback
        
        # No models available at all
        raise Exception("❌ No Gemini models available for generateContent")
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Error detecting Gemini model: {str(e)}")
        logger.error("=" * 60)
        logger.error("Using ultimate fallback: gemini-pro")
        # Ultimate fallback (may not work, but prevents crash)
        return 'gemini-pro'

def get_model_info():
    """Get information about the currently selected model"""
    try:
        model_name = f"models/{GEMINI_MODEL_NAME}"
        model = genai.get_model(model_name)
        return {
            'name': model.name,
            'display_name': model.display_name,
            'description': model.description,
            'input_token_limit': model.input_token_limit,
            'output_token_limit': model.output_token_limit,
            'supported_methods': model.supported_generation_methods
        }
    except Exception as e:
        return {
            'name': GEMINI_MODEL_NAME,
            'error': str(e)
        }

# Auto-detect and cache the best model on import
GEMINI_MODEL_NAME = get_best_available_model()

# Log model info
logger.info(f"📊 Model Info: {get_model_info()}")