"""
Model selector that chooses the appropriate LLM model based on question complexity.
Integrates with the complexity analyzer to route questions to deepseek-chat or deepseek-reasoner.
"""

from typing import Dict, Any, Optional
import logging
from .complexity_analyzer import analyze_question_complexity
from ..config import get_config

logger = logging.getLogger(__name__)


class ModelSelector:
    """Selects the appropriate model based on question complexity and configuration."""
    
    def __init__(self):
        self.config = get_config()
    
    def select_model_and_config(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        Select the appropriate model and return the configuration to use.
        
        Args:
            question (str): The question/goal being processed
            context (str): Additional context from previous steps
            
        Returns:
            Dict containing model selection information and configuration
        """
        # Get the active LLM configuration
        llm_config = self.config.llm
        active_config = llm_config.get_active_config()
        
        # Only do complexity routing for DeepSeek provider
        if llm_config.provider != "deepseek":
            logger.info(f"Complexity routing disabled for provider: {llm_config.provider}")
            return {
                'model': active_config.model,
                'is_complex': False,
                'complexity_analysis': None,
                'config': active_config,
                'routing_enabled': False
            }
        
        # Check if complexity routing is enabled
        if not hasattr(active_config, 'enable_complexity_routing') or not active_config.enable_complexity_routing:
            logger.info("Complexity routing disabled in configuration")
            return {
                'model': active_config.model,
                'is_complex': False,
                'complexity_analysis': None,
                'config': active_config,
                'routing_enabled': False
            }
        
        # Analyze question complexity
        complexity_analysis = analyze_question_complexity(question, context)
        is_complex = complexity_analysis['is_complex']
        
        # Get the appropriate model
        selected_model = active_config.get_model_for_complexity(is_complex)
        
        # Create a modified config with the selected model
        selected_config = self._create_config_with_model(active_config, selected_model)
        
        logger.info(
            f"Model selection: {selected_model} for question: '{question[:50]}...' "
            f"(complex: {is_complex})"
        )
        
        return {
            'model': selected_model,
            'is_complex': is_complex,
            'complexity_analysis': complexity_analysis,
            'config': selected_config,
            'routing_enabled': True
        }
    
    def _create_config_with_model(self, base_config, model: str):
        """Create a copy of the config with the specified model."""
        # Create a copy of the config object
        import copy
        config_copy = copy.deepcopy(base_config)
        config_copy.model = model
        return config_copy
    
    def get_complexity_stats(self, questions: list) -> Dict[str, Any]:
        """
        Analyze a batch of questions and return complexity statistics.
        Useful for understanding routing patterns.
        
        Args:
            questions (list): List of questions to analyze
            
        Returns:
            Dict containing statistics about complexity routing
        """
        if not questions:
            return {'total': 0, 'simple': 0, 'complex': 0, 'routing_enabled': False}
        
        llm_config = self.config.llm
        routing_enabled = (
            llm_config.provider == "deepseek" and 
            hasattr(llm_config.get_active_config(), 'enable_complexity_routing') and
            llm_config.get_active_config().enable_complexity_routing
        )
        
        if not routing_enabled:
            return {
                'total': len(questions),
                'simple': len(questions),  # All treated as simple when routing disabled
                'complex': 0,
                'routing_enabled': False
            }
        
        simple_count = 0
        complex_count = 0
        
        for question in questions:
            analysis = analyze_question_complexity(question)
            if analysis['is_complex']:
                complex_count += 1
            else:
                simple_count += 1
        
        return {
            'total': len(questions),
            'simple': simple_count,
            'complex': complex_count,
            'routing_enabled': True,
            'simple_percentage': (simple_count / len(questions)) * 100,
            'complex_percentage': (complex_count / len(questions)) * 100
        }


# Global model selector instance
_global_selector: Optional[ModelSelector] = None

def get_model_selector() -> ModelSelector:
    """Get the global model selector instance."""
    global _global_selector
    if _global_selector is None:
        _global_selector = ModelSelector()
    return _global_selector

def select_model_for_question(question: str, context: str = "") -> Dict[str, Any]:
    """
    Convenience function to select model for a question.
    
    Args:
        question (str): The question to analyze
        context (str): Additional context
        
    Returns:
        Dict containing model selection information
    """
    selector = get_model_selector()
    return selector.select_model_and_config(question, context)


# Example usage
if __name__ == "__main__":
    # Test the model selector
    selector = ModelSelector()
    
    test_questions = [
        "What's the weather today?",
        "Calculate 15 * 8", 
        "Design a comprehensive microservices architecture for an e-commerce platform",
        "How do I create a file?",
        "Analyze the trade-offs between different database architectures and recommend an optimal solution"
    ]
    
    print("Model Selection Results:")
    print("-" * 50)
    
    for question in test_questions:
        result = selector.select_model_and_config(question)
        print(f"\nQuestion: {question}")
        print(f"Selected Model: {result['model']}")
        print(f"Is Complex: {result['is_complex']}")
        print(f"Routing Enabled: {result['routing_enabled']}")
        if result['complexity_analysis']:
            print(f"Reasoning: {result['complexity_analysis']['reasoning']}")
    
    # Show statistics
    print("\n" + "="*50)
    stats = selector.get_complexity_stats(test_questions)
    print(f"Complexity Statistics: {stats}")
