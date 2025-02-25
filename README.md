# Automated Pipeline for Project Execution

This project implements an automated pipeline that processes a structured plan and a problem definition to generate, execute, and assemble code solutions. It supports executing steps both locally and on remote servers, with an optional Docker-based execution environment for containerized runs.

---

## Overview

The pipeline is designed to:
- **Load and parse a plan file:** Extract sections and corresponding steps.
- **Load a problem definition:** Validate and read the problem description.
- **Process each step:** Generate code based on individual steps, add execution blocks, save code to files, and execute each step with retry logic.
- **Assemble the solution:** Combine executed steps into a main solution file and run it.
- **Execute in Docker:** Optionally build and run the solution inside a Docker container.
- **Transfer to remote servers:** If configured, transfer the solution for remote execution.

---

## Project Structure

- **`main_pipeline.py`**  
  Contains the `MainPipeline` class that orchestrates the entire process including:
  - **`load_plan`**: Reads and parses the plan file, splitting it into sections and steps.
  - **`load_problem`**: Reads the problem definition from a file.
  - **`process_steps`**: Iterates over each step in the plan, generates code, and executes each step with error handling.
  - **`assemble_and_execute_solution`**: Combines the results of executed steps and runs the final solution.
  - **`run_docker_container`**: Manages Docker container execution for the solution.
  
- **Supporting Modules**
  - **`config.py`**: Provides the `PipelineConfig` for accessing configuration details such as log file paths, log levels, and remote server settings.
  - **`logger.py`**: Implements `LoggerSetup` to configure logging for the pipeline.
  - **`step_manager.py`**: Contains the `StepManager` which handles code generation, modification, and execution for each step.
  - **`solution_assembler.py`**: Provides the `SolutionAssembler` class to assemble and execute the final solution.
  - **`docker_manager.py`**: Manages Docker image building and container execution.

---

## Features

- **Modular Design:** Each component is encapsulated in its own module for maintainability and scalability.
- **Robust Error Handling:** Detailed logging for each step, including failures in file reading, code generation, execution, and Docker operations.
- **Remote Execution:** Ability to execute specific steps on remote servers based on configuration.
- **Docker Integration:** Containerized execution to ensure consistency across different environments.
- **Retry Mechanism:** Supports configurable maximum retries for executing steps and the assembled solution.

---

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://your-repository-url.git
   cd your-repository-directory
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   > Ensure you have Docker installed and running if you plan to use Docker-based execution.

---

## Usage

1. **Prepare Input Files**
   - **Plan File (`plan.txt`):** Define sections and steps using a consistent format. Each section should start with a header (e.g., `## 1. **Section Title**`) and include step entries formatted like `1. **Step Description**:`.
   - **Problem File (`problem.txt`):** Provide a non-empty problem definition that the pipeline will process.

2. **Configure the Pipeline**
   - Adjust configuration settings in the `PipelineConfig` (e.g., log file paths, remote server settings, solution directory, and maximum retries).

3. **Run the Pipeline**
   ```bash
   python main_pipeline.py --plan path/to/plan.txt --problem path/to/problem.txt
   ```

4. **Optional: Execute with Docker**
   - If Docker execution is enabled, the pipeline will build the Docker image and run the container. Check the logs for Docker-specific execution details.

---

## Configuration Details

- **Logging:**  
  The pipeline uses a logger (`PipelineLogger`) to capture info, warnings, and errors. Configure the log file and log level in your configuration file.

- **Remote Servers:**  
  The configuration may include a list of remote servers with parameters such as:
  - `hostname`
  - `steps_to_execute` (a list of step numbers to run remotely)
  - `execute_remotely` flag

- **Retry Mechanism:**  
  The maximum number of retries for step execution and solution assembly is configurable via the `PipelineConfig`.

---

## Code Flow Details

1. **Plan Loading & Parsing:**  
   The `load_plan` method reads the plan file, splits content into sections (using '---' as a delimiter), and uses regular expressions to extract section titles and step descriptions.

2. **Problem Definition Loading:**  
   The `load_problem` method reads the problem file and verifies that it is non-empty.

3. **Step Processing:**  
   For each step:
   - Code generation is performed using the `StepManager`.
   - The generated code is modified to include a main execution block.
   - The code is saved to a file.
   - The class name is extracted from the code for further processing.
   - If configured, remote execution settings are applied.
   - The step code is executed with a retry mechanism in place.

4. **Solution Assembly & Execution:**  
   The executed step codes are assembled into a main solution file and executed. If successful, the solution may be transferred to remote servers if required.

5. **Docker Container Execution:**  
   The `run_docker_container` method builds a Docker image and runs the solution inside a container. Execution logs are captured for troubleshooting.

---

## Troubleshooting

- **File Read Errors:**  
  Ensure that the file paths for `plan.txt` and `problem.txt` are correct and that the files are accessible.

- **Step Execution Failures:**  
  Check the logs for detailed error messages. The logs will indicate if code generation, saving, or execution failed for any specific step.

- **Docker Issues:**  
  Verify that Docker is installed, running, and properly configured to build and run images. Check the Docker logs for additional details if container execution fails.

---

## Contributing

Contributions are welcome! Please follow these guidelines:
- Fork the repository and create your branch from `main`.
- Ensure code follows the established modular and structured pattern.
- Update tests and documentation as needed.
- Submit pull requests for review.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
