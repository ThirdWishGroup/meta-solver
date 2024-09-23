import os
import subprocess
import sys
import time
import openai
import ast
from typing import Tuple, Optional, Dict, Any
import logging
from utils import create_directory
from ssh_manager import SSHManager

class StepManager:
    def __init__(self, config: Any):
        self.config = config
        self.steps_dir = self.config.get('steps_directory')
        create_directory(self.steps_dir)
        self.logger = logging.getLogger('PipelineLogger')

    def generate_step_code(self, step_description: str, problem_definition: str, step_number: int) -> Optional[str]:
        prompt = f"""
                    I am building a project with the following problem definition:
                    {problem_definition}

                    Step {step_number}: {step_description}

                    Requirements:
                    - Create a Python class named Step{step_number}.
                    - Implement an execute method within the class that performs the step's functionality.
                    - Include a __main__ block to allow the script to be run independently.
                    - Ensure the code is syntactically correct and follows best practices.
                    - Provide only the Python code without any explanations or comments.
                """
        max_retries = 3
        retries = 0
        while retries < max_retries:
            try:
                response = openai.completions.create(
                    model=self.config.get('openai_model'),
                    messages=[
                        {"role": "system", "content": "You are a professional Python programmer."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    n=1,
                    stop=None
                )
                code = response.choices[0].message.content.strip()
                if code:
                    self.logger.info(f"Generated code for Step {step_number}")
                else:
                    self.logger.error(f"No code returned for Step {step_number}")
                return code
            except openai.RateLimitError:
                self.logger.warning("Rate limit exceeded. Retrying after 10 seconds.")
                time.sleep(10)
                retries += 1
            except openai.OpenAIError as e:
                self.logger.error(f"OpenAI API error: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error during code generation: {e}")
                return None
        self.logger.error(f"Failed to generate code for Step {step_number} after {max_retries} retries.")
        return None

    def add_main_block(self, step_code: str, step_number: int) -> str:
        try:
            tree = ast.parse(step_code)
            has_main = any(
                isinstance(node, ast.If) and
                isinstance(node.test, ast.Compare) and
                isinstance(node.test.left, ast.Name) and
                node.test.left.id == '__name__' and
                any(isinstance(op, (ast.Eq, ast.Is)) for op in node.test.ops)
                for node in ast.walk(tree)
            )
            if not has_main:
                main_code = f"""

if __name__ == "__main__":
    step = Step{step_number}()
    step.execute()
"""
                step_code += main_code
                self.logger.info(f"Added __main__ block to Step {step_number}")
            return step_code
        except SyntaxError as e:
            self.logger.error(f"Syntax error while adding __main__ block: {e}")
            return step_code
        except Exception as e:
            self.logger.error(f"Unexpected error while adding __main__ block: {e}")
            return step_code

    def extract_class_name(self, step_code: str) -> Optional[str]:
        try:
            tree = ast.parse(step_code)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    self.logger.info(f"Extracted class name: {node.name}")
                    return node.name
            self.logger.error("No class definition found in step code.")
            return None
        except SyntaxError as e:
            self.logger.error(f"Syntax error while extracting class name: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error while extracting class name: {e}")
            return None

    def save_step_code(self, step_number: int, step_code: str) -> Optional[str]:
        step_filename = f'step_{step_number:03}.py'
        step_path = os.path.join(self.steps_dir, step_filename)
        try:
            with open(step_path, 'w', encoding='utf-8') as file:
                file.write(step_code)
            self.logger.info(f"Saved Step {step_number} to {step_path}")
            return step_path
        except IOError as e:
            self.logger.error(f"Failed to save Step {step_number}: {e}")
            return None

    def get_step_code(self, step_path: str) -> str:
        try:
            with open(step_path, 'r', encoding='utf-8') as file:
                return file.read()
        except IOError as e:
            self.logger.error(f"Failed to read step file {step_path}: {e}")
            return ""

    def update_step_code(self, step_path: str, new_code: str):
        try:
            with open(step_path, 'w', encoding='utf-8') as file:
                file.write(new_code)
            self.logger.info(f"Updated step code at {step_path}")
        except IOError as e:
            self.logger.error(f"Failed to update step file {step_path}: {e}")

    def run_step(self, step_path: str, execute_remotely: bool = False, server_config: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if execute_remotely and server_config:
            ssh_manager = SSHManager(server_config)
            if not ssh_manager.establish_connection():
                return False, "SSH connection failed."
            remote_path = f"/tmp/{os.path.basename(step_path)}"
            if not ssh_manager.transfer_file(step_path, remote_path):
                ssh_manager.close_connection()
                return False, "File transfer failed."
            out, err = ssh_manager.execute_command(f"python {remote_path}")
            ssh_manager.close_connection()
            if not err:
                self.logger.info(f"Successfully executed remote step: {step_path}")
                return True, out
            else:
                self.logger.error(f"Error executing remote step {step_path}: {err}")
                return False, err
        else:
            try:
                result = subprocess.run(
                    [sys.executable, step_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                self.logger.info(f"Successfully executed local step: {step_path}")
                return True, result.stdout
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error executing step {step_path}: {e.stderr}")
                return False, e.stderr
            except Exception as e:
                self.logger.error(f"Unexpected error during step execution: {e}")
                return False, "Execution failed."

    def fix_code_with_gpt4(self, error_message: str, step_code: str, step_number: int, problem_definition: str) -> Optional[str]:
        prompt = f"""
I encountered the following error while executing step {step_number} of my project:

Error Message:
{error_message}

Current Code:
```python
{step_code}
```

Problem Definition:
{problem_definition}

Requirements:
- Fix the error in the code above.
- Ensure the corrected code includes a Python class named Step{step_number} with an execute method.
- Provide only the corrected Python code without any explanations or comments.
"""
        max_retries = 3
        retries = 0
        while retries < max_retries:
            try:
                response = openai.chat.create(
                    model=self.config.get('openai_model'),
                    messages=[
                        {"role": "system", "content": "You are a professional Python programmer."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=1000,
                    n=1,
                    stop=None
                )
                corrected_code = response.choices[0].message.content.strip()
                if corrected_code:
                    self.logger.info(f"GPT-4 provided corrected code for Step {step_number}")
                else:
                    self.logger.error(f"No corrected code returned by GPT-4 for Step {step_number}")
                return corrected_code
            except openai.error.RateLimitError:
                self.logger.warning("Rate limit exceeded during code fixing. Retrying after 10 seconds.")
                time.sleep(10)
                retries += 1
            except openai.error.OpenAIError as e:
                self.logger.error(f"OpenAI API error during code fixing: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error during code fixing: {e}")
                return None
        self.logger.error(f"Failed to fix code for Step {step_number} after {max_retries} retries.")
        return None

    def execute_and_fix_step(self, step_path: str, step_number: int, problem_definition: str, max_retries: int,
                             execute_remotely: bool = False, server_config: Optional[Dict[str, Any]] = None) -> bool:
        retries = 0
        while retries < max_retries:
            success, output_or_error = self.run_step(step_path, execute_remotely, server_config)
            if success:
                return True
            else:
                self.logger.warning(f"Step {step_number} failed on attempt {retries + 1}: {output_or_error}")
                step_code = self.get_step_code(step_path)
                if not step_code:
                    self.logger.error(f"No code available to fix for Step {step_number}")
                    return False
                corrected_code = self.fix_code_with_gpt4(output_or_error, step_code, step_number, problem_definition)
                if corrected_code:
                    self.update_step_code(step_path, corrected_code)
                    retries += 1
                    time.sleep(2)
                else:
                    self.logger.error(f"Failed to fix code for Step {step_number}")
                    return False
        self.logger.error(f"Max retries exceeded for Step {step_number}")
        return False
