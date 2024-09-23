import os
import re
import subprocess
import sys
import ast
import time
from typing import List, Optional, Dict, Any, Tuple
import logging
from utils import create_directory
from ssh_manager import SSHManager
import openai

class SolutionAssembler:
    def __init__(self, config: Any):
        self.config = config
        self.solution_dir = self.config.get('solution_directory')
        self.steps_dir = self.config.get('steps_directory')
        create_directory(self.solution_dir)
        self.logger = logging.getLogger('PipelineLogger')

    def assemble_solution(self, executed_steps: List[str]) -> Optional[str]:
        main_imports = ""
        main_executions = ""
        for step_path in executed_steps:
            step_filename = os.path.basename(step_path)
            module_name = os.path.splitext(step_filename)[0]
            step_number_match = re.search(r'step_(\d+)\.py', step_filename)
            if not step_number_match:
                self.logger.warning(f"Filename does not match expected pattern: {step_filename}")
                continue
            step_number = step_number_match.group(1)
            step_code = self.get_step_code(step_path)
            if not step_code:
                self.logger.error(f"Failed to retrieve code from {step_path}")
                continue
            class_name = self.extract_class_name(step_code)
            if not class_name:
                self.logger.error(f"Failed to extract class name from {step_path}")
                continue
            main_imports += f"from steps.{module_name} import {class_name}\n"
            main_executions += f"    step{step_number} = {class_name}()\n"
            main_executions += f"    step{step_number}.execute()\n\n"
        
        if not main_imports and not main_executions:
            self.logger.error("No valid steps to assemble into solution.")
            return None
        
        main_code = f"""\
                        {main_imports}

                        def main():
                        {main_executions}

                        if __name__ == "__main__":
                            main()
                        """
        main_file_path = os.path.join(self.solution_dir, 'main.py')
        try:
            with open(main_file_path, 'w', encoding='utf-8') as file:
                file.write(main_code)
            self.logger.info(f"Assembled solution at {main_file_path}")
            return main_file_path
        except IOError as e:
            self.logger.error(f"Failed to write main.py: {e}")
            return None

    def get_step_code(self, step_path: str) -> str:
        try:
            with open(step_path, 'r', encoding='utf-8') as file:
                return file.read()
        except IOError as e:
            self.logger.error(f"Failed to read step file {step_path}: {e}")
            return ""

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

    def execute_main(self, main_file_path: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                [sys.executable, main_file_path],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"Successfully executed main.py")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error executing main.py: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            self.logger.error(f"Unexpected error during main execution: {e}")
            return False, "Execution failed."

    def fix_main_with_gpt4(self, error_message: str, main_code: str, problem_definition: str) -> Optional[str]:
        prompt = f"""
                I encountered the following error while executing the final main.py of my project:

                Error Message:
                {error_message}

                Current main.py Code:
                ```python
                {main_code}
                ```

                Problem Definition:
                {problem_definition}

                Requirements:
                - Fix the error in the main.py code above.
                - Ensure that main.py correctly imports and executes all step classes.
                - Provide only the corrected Python code without any explanations or comments.
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
                    max_tokens=1000,
                    n=1,
                    stop=None
                )
                corrected_code = response.choices[0].message.content.strip()
                if corrected_code:
                    self.logger.info("GPT-4 provided corrected main.py")
                else:
                    self.logger.error("No corrected code returned by GPT-4 for main.py")
                return corrected_code
            except openai.error.RateLimitError:
                self.logger.warning("Rate limit exceeded during main.py fixing. Retrying after 10 seconds.")
                time.sleep(10)
                retries += 1
            except openai.error.OpenAIError as e:
                self.logger.error(f"OpenAI API error during main.py fixing: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Unexpected error during main.py fixing: {e}")
                return None
        self.logger.error("Failed to fix main.py after multiple retries.")
        return None

    def execute_and_fix_main(self, main_file_path: str, problem_definition: str, max_retries: int) -> bool:
        retries = 0
        while retries < max_retries:
            success, output_or_error = self.execute_main(main_file_path)
            if success:
                return True
            else:
                self.logger.warning(f"main.py failed on attempt {retries + 1}: {output_or_error}")
                main_code = self.get_main_code(main_file_path)
                if not main_code:
                    self.logger.error("No code available to fix for main.py")
                    return False
                corrected_code = self.fix_main_with_gpt4(output_or_error, main_code, problem_definition)
                if corrected_code:
                    self.update_main_code(main_file_path, corrected_code)
                    retries += 1
                    time.sleep(2)
                else:
                    self.logger.error("Failed to fix main.py")
                    return False
        self.logger.error("Max retries exceeded for main.py")
        return False

    def get_main_code(self, main_file_path: str) -> str:
        try:
            with open(main_file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except IOError as e:
            self.logger.error(f"Failed to read main.py: {e}")
            return ""

    def update_main_code(self, main_file_path: str, new_code: str):
        try:
            with open(main_file_path, 'w', encoding='utf-8') as file:
                file.write(new_code)
            self.logger.info("Updated main.py with corrected code.")
        except IOError as e:
            self.logger.error(f"Failed to update main.py: {e}")

    def transfer_solution_to_remote(self, solution_dir: str, server_config: Dict[str, Any]) -> bool:
        ssh_manager = SSHManager(server_config)
        if not ssh_manager.establish_connection():
            return False
        remote_solution_dir = f"/home/{server_config['username']}/solution"
        try:
            # Create remote solution directory
            ssh_manager.execute_command(f"mkdir -p {remote_solution_dir}")

            for root, dirs, files in os.walk(solution_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_path, solution_dir)
                    remote_path = os.path.join(remote_solution_dir, relative_path).replace('\\', '/')
                    remote_dir = os.path.dirname(remote_path)
                    ssh_manager.execute_command(f"mkdir -p {remote_dir}")
                    if not ssh_manager.transfer_file(local_path, remote_path):
                        self.logger.error(f"Failed to transfer file {local_path} to {remote_path}")
                        ssh_manager.close_connection()
                        return False
            ssh_manager.close_connection()
            self.logger.info(f"Successfully transferred solution to remote server: {server_config['hostname']}")
            return True
        except Exception as e:
            self.logger.error(f"Exception during solution transfer: {e}")
            ssh_manager.close_connection()
            return False
