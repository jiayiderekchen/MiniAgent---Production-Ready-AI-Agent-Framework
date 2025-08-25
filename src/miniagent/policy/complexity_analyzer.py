"""
Complexity analyzer for determining whether a question requires simple or complex reasoning.
Used to choose between deepseek-chat (simple) and deepseek-reasoner (complex) models.
"""

import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ComplexityAnalyzer:
    """Analyzes the complexity of questions to determine appropriate model selection."""
    
    def __init__(self):
        # Keywords that indicate complex reasoning tasks
        self.complex_keywords = {
            'mathematical': [
                'prove', 'derive', 'theorem', 'equation', 'integral', 'derivative',
                'optimization', 'algorithm', 'mathematical proof', 'statistical analysis',
                'probability distribution', 'regression', 'hypothesis testing'
            ],
            'logical': [
                'analyze', 'reasoning', 'logic', 'deduction', 'induction', 'inference',
                'causality', 'correlation', 'implications', 'consequences', 'paradox',
                'philosophical', 'ethical dilemma', 'moral reasoning'
            ],
            'strategic': [
                'strategy', 'planning', 'optimization', 'decision tree', 'cost-benefit',
                'trade-off', 'prioritize', 'feasibility', 'risk assessment', 'scenario analysis',
                'business plan', 'market analysis', 'competitive analysis'
            ],
            'creative': [
                'creative', 'innovative', 'brainstorm', 'design', 'architect', 'invent',
                'novel approach', 'alternative solution', 'think outside the box',
                'unconventional', 'original idea'
            ],
            'research': [
                'research', 'investigate', 'comprehensive analysis', 'literature review',
                'systematic study', 'data mining', 'trend analysis', 'comparative study',
                'longitudinal study', 'meta-analysis'
            ],
            'complex_programming': [
                'architecture', 'design pattern', 'refactor', 'optimize performance',
                'scalability', 'distributed system', 'microservices', 'algorithm design',
                'data structure optimization', 'system design', 'code review'
            ]
        }
        
        # Keywords that indicate simple tasks
        self.simple_keywords = [
            'what is', 'define', 'explain', 'describe', 'list', 'show', 'tell me',
            'how to', 'when', 'where', 'who', 'which', 'basic', 'simple',
            'calculate', 'convert', 'translate', 'find', 'search', 'lookup',
            'weather', 'time', 'date', 'current', 'today', 'now'
        ]
        
        # Question patterns that indicate complexity
        self.complex_patterns = [
            r'\b(?:why|how).*?(?:work|function|operate).*?(?:complex|complicated|sophisticated)\b',
            r'\bcompare.*?(?:and|vs|versus).*?(?:analyze|evaluation|assessment)\b',
            r'\b(?:pros and cons|advantages and disadvantages)\b',
            r'\b(?:step by step|detailed|comprehensive).*?(?:analysis|explanation|guide)\b',
            r'\b(?:multiple|several|various).*?(?:factors|considerations|aspects)\b',
            r'\b(?:cause|reason|factor).*?(?:behind|for|why)\b',
            r'\b(?:predict|forecast|estimate).*?(?:future|outcome|result)\b',
            r'\b(?:what if|suppose|imagine|consider)\b',
            r'\b(?:recommend|suggest|advise).*?(?:strategy|approach|solution)\b'
        ]
        
        # Simple patterns
        self.simple_patterns = [
            r'\bwhat is\b',
            r'\bhow to\b.*?\b(?:basic|simple|quick)\b',
            r'\b(?:current|today|now)\b.*?\b(?:weather|time|date)\b',
            r'\bcalculate\s+\d+',
            r'\bconvert\s+\d+',
            r'\b(?:show|list|display)\b'
        ]

    def analyze_complexity(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        Analyze the complexity of a question.
        
        Args:
            question (str): The question to analyze
            context (str): Additional context about previous steps
            
        Returns:
            Dict containing complexity assessment and reasoning
        """
        question_lower = question.lower()
        context_lower = context.lower() if context else ""
        full_text = f"{question_lower} {context_lower}"
        
        # Calculate complexity scores
        simple_score = self._calculate_simple_score(question_lower)
        complex_score = self._calculate_complex_score(full_text)
        
        # Additional complexity indicators
        length_complexity = self._analyze_length_complexity(question)
        structure_complexity = self._analyze_structure_complexity(question)
        
        # Combine scores
        total_simple_score = simple_score
        total_complex_score = complex_score + length_complexity + structure_complexity
        
        # Determine complexity
        is_complex = total_complex_score > total_simple_score and total_complex_score >= 2
        
        # Choose model
        recommended_model = "deepseek-reasoner" if is_complex else "deepseek-chat"
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            simple_score, complex_score, length_complexity, 
            structure_complexity, is_complex
        )
        
        result = {
            'is_complex': is_complex,
            'recommended_model': recommended_model,
            'scores': {
                'simple': total_simple_score,
                'complex': total_complex_score,
                'length_complexity': length_complexity,
                'structure_complexity': structure_complexity
            },
            'reasoning': reasoning
        }
        
        logger.info(f"Complexity analysis for '{question[:50]}...': {recommended_model} (complex: {is_complex})")
        logger.debug(f"Complexity scores: {result['scores']}")
        
        return result

    def _calculate_simple_score(self, text: str) -> float:
        """Calculate score for simple question indicators."""
        score = 0.0
        
        # Check for simple keywords
        for keyword in self.simple_keywords:
            if keyword in text:
                score += 1.0
        
        # Check for simple patterns
        for pattern in self.simple_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1.5
                
        return score

    def _calculate_complex_score(self, text: str) -> float:
        """Calculate score for complex reasoning indicators."""
        score = 0.0
        
        # Check for complex keywords by category
        for category, keywords in self.complex_keywords.items():
            category_score = 0
            for keyword in keywords:
                if keyword in text:
                    category_score += 1
            
            # Bonus for multiple keywords in same category
            if category_score > 1:
                score += category_score * 1.5
            elif category_score == 1:
                score += 1.0
        
        # Check for complex patterns
        for pattern in self.complex_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 2.0
                
        return score

    def _analyze_length_complexity(self, question: str) -> float:
        """Analyze complexity based on question length and structure."""
        words = question.split()
        word_count = len(words)
        
        # Longer questions tend to be more complex
        if word_count > 20:
            return 1.5
        elif word_count > 15:
            return 1.0
        elif word_count > 10:
            return 0.5
        else:
            return 0.0

    def _analyze_structure_complexity(self, question: str) -> float:
        """Analyze complexity based on question structure."""
        score = 0.0
        
        # Multiple questions or clauses
        if '?' in question and question.count('?') > 1:
            score += 1.0
        
        # Conditional statements
        if any(word in question.lower() for word in ['if', 'when', 'unless', 'provided that']):
            score += 0.5
        
        # Multiple conjunctions indicating complex relationships
        conjunctions = ['and', 'but', 'however', 'moreover', 'furthermore', 'nevertheless']
        conjunction_count = sum(1 for conj in conjunctions if conj in question.lower())
        if conjunction_count >= 2:
            score += 1.0
        elif conjunction_count == 1:
            score += 0.5
            
        return score

    def _generate_reasoning(self, simple_score: float, complex_score: float, 
                          length_complexity: float, structure_complexity: float, 
                          is_complex: bool) -> str:
        """Generate human-readable reasoning for the complexity assessment."""
        reasoning_parts = []
        
        if simple_score > 0:
            reasoning_parts.append(f"Simple indicators (score: {simple_score})")
        
        if complex_score > 0:
            reasoning_parts.append(f"Complex reasoning indicators (score: {complex_score})")
            
        if length_complexity > 0:
            reasoning_parts.append(f"Length complexity (score: {length_complexity})")
            
        if structure_complexity > 0:
            reasoning_parts.append(f"Structural complexity (score: {structure_complexity})")
        
        total_scores = f"Total: Simple={simple_score}, Complex={complex_score + length_complexity + structure_complexity}"
        
        model_choice = "deepseek-reasoner (complex reasoning)" if is_complex else "deepseek-chat (simple query)"
        
        return f"{'; '.join(reasoning_parts)}. {total_scores}. Recommended: {model_choice}"


def analyze_question_complexity(question: str, context: str = "") -> Dict[str, Any]:
    """
    Convenience function to analyze question complexity.
    
    Args:
        question (str): The question to analyze
        context (str): Additional context
        
    Returns:
        Dict containing complexity analysis results
    """
    analyzer = ComplexityAnalyzer()
    return analyzer.analyze_complexity(question, context)


# Example usage and testing
if __name__ == "__main__":
    analyzer = ComplexityAnalyzer()
    
    # Test cases
    test_questions = [
        "What's the weather today?",
        "Calculate 15 * 8",
        "How do I create a file in Python?",
        "Analyze the pros and cons of microservices architecture and recommend an optimal strategy for a high-traffic e-commerce platform",
        "Design a comprehensive algorithm for optimizing distributed database performance considering multiple factors like latency, consistency, and scalability",
        "What is the current time?",
        "Prove that the sum of squares of two consecutive integers is always odd",
        "Explain the philosophical implications of artificial intelligence on human consciousness and free will"
    ]
    
    for question in test_questions:
        result = analyzer.analyze_complexity(question)
        print(f"\nQuestion: {question}")
        print(f"Model: {result['recommended_model']}")
        print(f"Complex: {result['is_complex']}")
        print(f"Reasoning: {result['reasoning']}")
