import asyncio
import time
import json
from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class EvalResult:
    """Result of a single evaluation"""
    task_id: str
    success: bool
    score: float
    execution_time: float
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalTask:
    """Definition of an evaluation task"""
    id: str
    description: str
    goal: str
    expected_output: Any = None
    success_criteria: Callable[[Any], bool] = None
    max_steps: int = 10
    timeout_s: float = 60.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalSuite:
    """Collection of evaluation tasks"""
    name: str
    description: str
    tasks: List[EvalTask] = field(default_factory=list)
    
    def add_task(self, task: EvalTask):
        """Add a task to the suite"""
        self.tasks.append(task)

class AgentEvaluator:
    """Comprehensive agent evaluation framework"""
    
    def __init__(self, output_dir: str = "./eval_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    async def run_single_task(self, task: EvalTask, agent_fn: Callable[[str, int], Any]) -> EvalResult:
        """Run a single evaluation task"""
        start_time = time.time()
        
        try:
            # Run the agent with timeout
            result = await asyncio.wait_for(
                agent_fn(task.goal, task.max_steps),
                timeout=task.timeout_s
            )
            
            execution_time = time.time() - start_time
            
            # Determine success
            success = False
            score = 0.0
            
            if task.success_criteria:
                try:
                    success = task.success_criteria(result)
                    score = 1.0 if success else 0.0
                except Exception as e:
                    logger.warning(f"Success criteria failed for task {task.id}: {e}")
            else:
                # Default success: no error and has result
                success = not isinstance(result, dict) or "error" not in result
                score = 1.0 if success else 0.0
            
            return EvalResult(
                task_id=task.id,
                success=success,
                score=score,
                execution_time=execution_time,
                output=result,
                metadata={"task_description": task.description}
            )
            
        except asyncio.TimeoutError:
            return EvalResult(
                task_id=task.id,
                success=False,
                score=0.0,
                execution_time=task.timeout_s,
                output=None,
                error="Task timed out",
                metadata={"task_description": task.description}
            )
        except Exception as e:
            execution_time = time.time() - start_time
            return EvalResult(
                task_id=task.id,
                success=False,
                score=0.0,
                execution_time=execution_time,
                output=None,
                error=str(e),
                metadata={"task_description": task.description}
            )
    
    async def run_suite(self, suite: EvalSuite, agent_fn: Callable[[str, int], Any]) -> Dict[str, Any]:
        """Run a complete evaluation suite"""
        logger.info(f"Running evaluation suite: {suite.name}")
        
        results = []
        total_tasks = len(suite.tasks)
        
        for i, task in enumerate(suite.tasks):
            logger.info(f"Running task {i+1}/{total_tasks}: {task.id}")
            result = await self.run_single_task(task, agent_fn)
            results.append(result)
        
        # Calculate overall metrics
        successful_tasks = sum(1 for r in results if r.success)
        total_score = sum(r.score for r in results)
        total_time = sum(r.execution_time for r in results)
        
        suite_result = {
            "suite_name": suite.name,
            "suite_description": suite.description,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "average_score": total_score / total_tasks if total_tasks > 0 else 0,
            "total_execution_time": total_time,
            "average_execution_time": total_time / total_tasks if total_tasks > 0 else 0,
            "results": [self._result_to_dict(r) for r in results]
        }
        
        # Save results
        self._save_results(suite_result)
        
        return suite_result
    
    def _result_to_dict(self, result: EvalResult) -> Dict[str, Any]:
        """Convert EvalResult to dictionary"""
        return {
            "task_id": result.task_id,
            "success": result.success,
            "score": result.score,
            "execution_time": result.execution_time,
            "output": result.output,
            "error": result.error,
            "metadata": result.metadata
        }
    
    def _save_results(self, results: Dict[str, Any]):
        """Save evaluation results to file"""
        timestamp = int(time.time())
        filename = f"eval_{results['suite_name']}_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Saved evaluation results to {filepath}")


def create_basic_eval_suite() -> EvalSuite:
    """Create a basic evaluation suite for testing agent capabilities"""
    suite = EvalSuite(
        name="basic_capabilities",
        description="Basic evaluation of agent capabilities"
    )
    
    # Math calculation task
    def check_math_result(result):
        if isinstance(result, dict) and "result" in result:
            return "12" in str(result["result"]) or "12.0" in str(result["result"])
        return False
    
    suite.add_task(EvalTask(
        id="math_simple",
        description="Simple math calculation",
        goal="Calculate 3 * 4",
        success_criteria=check_math_result,
        max_steps=3
    ))
    
    # File operations task
    def check_file_result(result):
        if isinstance(result, dict) and "result" in result:
            return "created" in str(result["result"]).lower() or "written" in str(result["result"]).lower()
        return False
    
    suite.add_task(EvalTask(
        id="file_operations",
        description="Basic file operations",
        goal="Create a file called 'test.txt' with the content 'Hello World'",
        success_criteria=check_file_result,
        max_steps=5
    ))
    
    # Information synthesis task
    def check_synthesis_result(result):
        if isinstance(result, dict) and "result" in result:
            result_text = str(result["result"]).lower()
            return len(result_text) > 50 and ("agent" in result_text or "ai" in result_text)
        return False
    
    suite.add_task(EvalTask(
        id="information_synthesis",
        description="Information synthesis and reasoning",
        goal="Explain what an AI agent is and give 3 key capabilities",
        success_criteria=check_synthesis_result,
        max_steps=5
    ))
    
    return suite


def create_advanced_eval_suite() -> EvalSuite:
    """Create an advanced evaluation suite for complex capabilities"""
    suite = EvalSuite(
        name="advanced_capabilities",
        description="Advanced evaluation of complex agent capabilities"
    )
    
    # Problem solving task
    def check_problem_solving(result):
        if isinstance(result, dict) and "result" in result:
            result_text = str(result["result"]).lower()
            return any(keyword in result_text for keyword in ["solution", "approach", "strategy", "method"])
        return False
    
    suite.add_task(EvalTask(
        id="problem_solving",
        description="Multi-step problem solving",
        goal="You need to organize a small meeting. List the steps you would take and create a simple agenda",
        success_criteria=check_problem_solving,
        max_steps=8
    ))
    
    # Code generation task
    def check_code_generation(result):
        if isinstance(result, dict) and "result" in result:
            result_text = str(result["result"]).lower()
            return "def" in result_text or "function" in result_text or "print" in result_text
        return False
    
    suite.add_task(EvalTask(
        id="code_generation",
        description="Simple code generation",
        goal="Write a Python function that calculates the factorial of a number",
        success_criteria=check_code_generation,
        max_steps=5
    ))
    
    # Research and analysis task
    def check_research_analysis(result):
        if isinstance(result, dict) and "result" in result:
            result_text = str(result["result"])
            return len(result_text) > 200 and any(keyword in result_text.lower() for keyword in ["analysis", "research", "findings", "conclusion"])
        return False
    
    suite.add_task(EvalTask(
        id="research_analysis",
        description="Research and analysis task",
        goal="Research the benefits of artificial intelligence and provide a brief analysis with pros and cons",
        success_criteria=check_research_analysis,
        max_steps=10
    ))
    
    return suite


# Legacy function for backward compatibility
def run_task(task_fn: Callable[[], Any]) -> Dict[str, Any]:
    """Legacy function for backward compatibility"""
    try:
        out = task_fn()
        return {"ok": True, "output": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}
