import os
import subprocess
import docker
import paramiko
import tempfile
from typing import Any, List, Tuple, Optional, Dict
from logger import LoggerSetup

class DockerManager:
    """
    Manages Docker operations for executing Python projects.
    
    Attributes:
        docker_client (docker.DockerClient): The Docker client used to manage images and containers.
        image_name (str): The name/tag of the Docker image.
        container_name (str): The name of the Docker container.
        logger (logging.Logger): Logger for logging Docker operations.
    """
    
    def __init__(self, image_name: str = "python-executor:latest", container_name: str = "python-executor-container") -> None:
        """
        Initializes the DockerManager with specified image and container names.
        
        Args:
            image_name (str): The name/tag for the Docker image.
            container_name (str): The name for the Docker container.
        """
        self.docker_client: docker.DockerClient = docker.from_env()
        self.image_name: str = image_name
        self.container_name: str = container_name
        self.logger = LoggerSetup('docker_manager.log', 'INFO').logger
        self._ensure_image()

    def _ensure_image(self) -> None:
        """
        Ensures that the Docker image exists, building it if necessary.
        """
        try:
            self.docker_client.images.get(self.image_name)
            self.logger.info(f"Docker image '{self.image_name}' already exists.")
        except docker.errors.ImageNotFound:
            self.logger.info(f"Docker image '{self.image_name}' not found. Building a new one.")
            dockerfile = """
            FROM python:3.10-slim

            # Set work directory
            WORKDIR /app

            # Install dependencies
            COPY requirements.txt .
            RUN pip install --no-cache-dir -r requirements.txt

            # Copy entrypoint script
            COPY entrypoint.sh /entrypoint.sh
            RUN chmod +x /entrypoint.sh

            ENTRYPOINT ["/entrypoint.sh"]
            """
            entrypoint = """#!/bin/bash
            python main.py
            """

            with tempfile.TemporaryDirectory() as build_dir:
                dockerfile_path = os.path.join(build_dir, 'Dockerfile')
                with open(dockerfile_path, 'w') as df:
                    df.write(dockerfile)
                
                entrypoint_path = os.path.join(build_dir, 'entrypoint.sh')
                with open(entrypoint_path, 'w') as ep:
                    ep.write(entrypoint)
                
                # Create a minimal requirements.txt if not present
                requirements_path = os.path.join(build_dir, 'requirements.txt')
                if not os.path.exists(requirements_path):
                    with open(requirements_path, 'w') as req:
                        req.write("")

                self.docker_client.images.build(path=build_dir, dockerfile=dockerfile_path, tag=self.image_name)
                self.logger.info(f"Docker image '{self.image_name}' built successfully.")

    def build_image(self, context_path: str, dockerfile_path: str) -> None:
        """
        Builds a Docker image from the specified context and Dockerfile.
        
        Args:
            context_path (str): Path to the build context.
            dockerfile_path (str): Path to the Dockerfile.
        """
        try:
            image, logs = self.docker_client.images.build(path=context_path, dockerfile=dockerfile_path, tag=self.image_name)
            for chunk in logs:
                if 'stream' in chunk:
                    for line in chunk['stream'].splitlines():
                        self.logger.debug(line)
            self.logger.info(f"Docker image '{self.image_name}' built successfully.")
        except docker.errors.BuildError as e:
            self.logger.error(f"Failed to build Docker image: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during Docker image build: {e}")
            raise

    def run_container(self, host_project_dir: str, container_project_dir: str = "/app") -> Tuple[bool, str]:
        """
        Runs a Docker container from the built image, mounting the project directory.
        
        Args:
            host_project_dir (str): Path to the project directory on the host.
            container_project_dir (str): Path inside the container where the project will be mounted.
        
        Returns:
            Tuple[bool, str]: Success status and container logs/output.
        """
        try:
            try:
                existing_container = self.docker_client.containers.get(self.container_name)
                existing_container.remove(force=True)
                self.logger.info(f"Removed existing container '{self.container_name}'.")
            except docker.errors.NotFound:
                self.logger.info(f"No existing container named '{self.container_name}' found. Proceeding to create a new one.")

            # Run the container
            container = self.docker_client.containers.run(
                self.image_name,
                name=self.container_name,
                volumes={
                    os.path.abspath(host_project_dir): {
                        'bind': container_project_dir,
                        'mode': 'rw'
                    }
                },
                detach=True,
                tty=True
            )
            self.logger.info(f"Docker container '{self.container_name}' started.")

            # Wait for the container to finish execution
            exit_status = container.wait()
            logs = container.logs().decode()
            self.logger.info(f"Container '{self.container_name}' exited with status {exit_status}.")
            self.logger.debug(f"Container logs:\n{logs}")

            return_code = exit_status.get('StatusCode', 1)
            success = return_code == 0
            return success, logs
        except docker.errors.ContainerError as e:
            self.logger.error(f"Container error: {e}")
            return False, str(e)
        except Exception as e:
            self.logger.error(f"Unexpected error while running container: {e}")
            return False, str(e)

    def cleanup_container(self) -> None:
        """
        Removes the Docker container if it exists.
        """
        try:
            container = self.docker_client.containers.get(self.container_name)
            container.remove(force=True)
            self.logger.info(f"Docker container '{self.container_name}' removed.")
        except docker.errors.NotFound:
            self.logger.info(f"No container named '{self.container_name}' found for cleanup.")
        except Exception as e:
            self.logger.error(f"Unexpected error during container cleanup: {e}")

    def push_image(self, repository: str, tag: Optional[str] = None) -> None:
        """
        Pushes the Docker image to a specified repository.
        
        Args:
            repository (str): The Docker repository to push the image to.
            tag (Optional[str]): The tag for the Docker image.
        """
        try:
            full_image_name = f"{repository}:{tag}" if tag else self.image_name
            for line in self.docker_client.images.push(repository, tag=tag, stream=True, decode=True):
                self.logger.debug(line)
            self.logger.info(f"Docker image '{full_image_name}' pushed to repository '{repository}'.")
        except docker.errors.APIError as e:
            self.logger.error(f"Failed to push Docker image: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during Docker image push: {e}")
            raise

