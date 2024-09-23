
import sys
import logging
import re
import ast
from typing import List, Dict, Any
from config import PipelineConfig
from logger import LoggerSetup
from step_manager import StepManager
from solution_assembler import SolutionAssembler
from docker_manager import DockerManager

class MainPipeline:
    def __init__(self, plan_path: str, problem_path: str, config: PipelineConfig):
        self.plan_path = plan_path
        self.problem_path = problem_path
        self.config = config
        self.step_manager = StepManager(config)
        self.solution_assembler = SolutionAssembler(config)
        self.logger = logging.getLogger('PipelineLogger')

    def load_plan(self) -> Dict[str, List[str]]:
            """
            Loads and parses the plan file, extracting sections and their corresponding steps.

            Returns:
                Dict[str, List[str]]: A dictionary where keys are section titles and values are lists of step descriptions.
            """
            try:
                with open(self.plan_path, 'r', encoding='utf-8') as file:
                    content = file.read()
            except IOError as e:
                self.logger.error(f"Failed to read plan file {self.plan_path}: {e}")
                sys.exit(1)
            
            # Split the content into sections using '---' as the delimiter
            sections = content.split('---')
            plan = {}
            section_pattern = re.compile(r'^##\s+\d+\.\s+\*\*(.+?)\*\*', re.MULTILINE)
            step_pattern = re.compile(r'^\s*\d+\.\s+\*\*(.+?)\*\*:', re.MULTILINE)

            for section in sections:
                # Extract the section title
                section_match = section_pattern.search(section)
                if section_match:
                    section_title = section_match.group(1).strip()
                    # Extract all steps within the section
                    steps = step_pattern.findall(section)
                    if steps:
                        # Clean step titles by removing any trailing colons and whitespace
                        cleaned_steps = [step.strip().rstrip(':') for step in steps]
                        plan[section_title] = cleaned_steps
                    else:
                        self.logger.warning(f"No steps found in section: '{section_title}'")
            if not plan:
                self.logger.error("No valid plan sections found in plan file.")
                sys.exit(1)
            self.logger.info(f"Loaded plan with sections: {list(plan.keys())}")
            return plan

    def load_problem(self) -> str:
        try:
            with open(self.problem_path, 'r', encoding='utf-8') as file:
                problem_definition = file.read().strip()
                if not problem_definition:
                    self.logger.error("Problem definition is empty.")
                    sys.exit(1)
                return problem_definition
        except IOError as e:
            self.logger.error(f"Failed to read problem file {self.problem_path}: {e}")
            sys.exit(1)

    def process_steps(self, plan: Dict[str, List[str]], problem_definition: str) -> List[str]:
        executed_steps = []
        step_counter = 1
        for title, steps in plan.items():
            for step in steps:
                self.logger.info(f"Processing Step {step_counter}: {step}")
                step_code = self.step_manager.generate_step_code(step, problem_definition, step_counter)
                if not step_code:
                    self.logger.error(f"Failed to generate code for Step {step_counter}")
                    step_counter += 1
                    continue
                step_code = self.step_manager.add_main_block(step_code, step_counter)
                step_path = self.step_manager.save_step_code(step_counter, step_code)
                if not step_path:
                    self.logger.error(f"Failed to save Step {step_counter}")
                    step_counter += 1
                    continue
                class_name = self.step_manager.extract_class_name(step_code)
                if not class_name:
                    self.logger.error(f"Failed to extract class name for Step {step_counter}")
                    step_counter += 1
                    continue
                execute_remotely = False
                server_config = None
                for server in self.config.get('remote_servers'):
                    # Ensure steps_to_execute contains integers
                    steps_to_execute = server.get('steps_to_execute', [])
                    if isinstance(steps_to_execute, list):
                        if step_counter in steps_to_execute:
                            execute_remotely = server.get('execute_remotely', False)
                            server_config = server
                            break
                success = self.step_manager.execute_and_fix_step(
                    step_path,
                    step_counter,
                    problem_definition,
                    self.config.get('max_retries'),
                    execute_remotely,
                    server_config
                )
                if success:
                    executed_steps.append(step_path)
                    self.logger.info(f"Successfully executed Step {step_counter}")
                else:
                    self.logger.error(f"Failed to execute Step {step_counter}")
                step_counter += 1
        return executed_steps

    def assemble_and_execute_solution(self, executed_steps: List[str], problem_definition: str) -> bool:
        main_file_path = self.solution_assembler.assemble_solution(executed_steps)
        if not main_file_path:
            self.logger.error("Failed to assemble solution.")
            return False
        success = self.solution_assembler.execute_and_fix_main(
            main_file_path,
            problem_definition,
            self.config.get('max_retries')
        )
        if success:
            self.logger.info("Successfully executed assembled solution.")
        else:
            self.logger.error("Failed to execute assembled solution.")
        return success
    
    def run_docker_container(self) -> bool:
        """
        Builds the Docker image, runs the container, and captures the execution result.
        
        Returns:
            bool: True if execution inside Docker was successful, False otherwise.
        """
        docker_manager = DockerManager()
        project_dir = self.config.get('solution_directory')

        self.logger.info("Starting Docker container to execute the solution.")
        success, logs = docker_manager.run_container(host_project_dir=project_dir)
        
        if success:
            self.logger.info("Docker container executed the solution successfully.")
            self.logger.debug(f"Docker Logs:\n{logs}")
            return True
        else:
            self.logger.error("Docker container failed to execute the solution.")
            self.logger.error(f"Docker Logs:\n{logs}")
            return False

    def run(self):
        plan = self.load_plan()
        problem = self.load_problem()
        executed_steps = self.process_steps(plan, problem)
        if not executed_steps:
            self.logger.error("No steps were successfully executed.")
            sys.exit(1)
        success = self.assemble_and_execute_solution(executed_steps, problem)
        if success:
            for server in self.config.get('remote_servers'):
                steps_to_execute = server.get('steps_to_execute', [])
                if server.get('execute_remotely') and steps_to_execute:
                    self.logger.info(f"Transferring solution to remote server: {server['hostname']}")
                    transfer_success = self.solution_assembler.transfer_solution_to_remote(
                        self.solution_assembler.solution_dir,
                        server
                    )
                    if not transfer_success:
                        self.logger.error(f"Failed to transfer solution to {server['hostname']}")
        else:
            self.logger.error("Pipeline execution failed.")
            sys.exit(1)

def parse_arguments():
    import argparse
    parser = argparse.ArgumentParser(description='Automated Pipeline for Project Execution.')
    parser.add_argument('--plan', type=str, default='plan.txt', help='Path to plan.txt')
    parser.add_argument('--problem', type=str, default='problem.txt', help='Path to problem.txt')
    return parser.parse_args()

def main():
    args = parse_arguments()
    config = PipelineConfig()
    LoggerSetup(config.get('log_file'), config.get('log_level'))
    pipeline = MainPipeline(args.plan, args.problem, config)
    pipeline.run()

if __name__ == "__main__":
    main()
