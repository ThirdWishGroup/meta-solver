import os
import yaml
from typing import Dict, Any

class PipelineConfig:
    CONFIG_FILE = 'config.yaml'
    DEFAULT_CONFIG = {
        'steps_directory': 'steps',
        'solution_directory': 'solution',
        'max_retries': 5,
        'openai_model': 'gpt-4',
        'log_file': 'pipeline.log',
        'log_level': 'INFO',
        'remote_servers': [
            {
                'hostname': 'remote.server.com',
                'port': 22,
                'username': 'user',
                'password': None,
                'ssh_key_path': '/app/.ssh/id_rsa',
                'execute_remotely': False,
                'steps_to_execute': []
            }
        ]
    }

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.config = self.load_config()
        self.validate_config()

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            with open(self.config_path, 'w') as file:
                yaml.dump(self.DEFAULT_CONFIG, file)
            return self.DEFAULT_CONFIG.copy()
        else:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file) or {}
            for key, value in self.DEFAULT_CONFIG.items():
                config.setdefault(key, value)
            return config

    def validate_config(self):
        if not isinstance(self.config.get('steps_directory'), str):
            raise ValueError("steps_directory must be a string.")
        if not isinstance(self.config.get('solution_directory'), str):
            raise ValueError("solution_directory must be a string.")
        if not isinstance(self.config.get('max_retries'), int):
            raise ValueError("max_retries must be an integer.")
        if not isinstance(self.config.get('openai_model'), str):
            raise ValueError("openai_model must be a string.")
        if not isinstance(self.config.get('log_file'), str):
            raise ValueError("log_file must be a string.")
        if not isinstance(self.config.get('log_level'), str):
            raise ValueError("log_level must be a string.")
        if not isinstance(self.config.get('remote_servers'), list):
            raise ValueError("remote_servers must be a list.")
        for server in self.config.get('remote_servers'):
            if not isinstance(server.get('hostname'), str):
                raise ValueError("hostname in remote_servers must be a string.")
            if not isinstance(server.get('port'), int):
                raise ValueError("port in remote_servers must be an integer.")
            if not isinstance(server.get('username'), str):
                raise ValueError("username in remote_servers must be a string.")
            if not isinstance(server.get('password'), (str, type(None))):
                raise ValueError("password in remote_servers must be a string or None.")
            if not isinstance(server.get('ssh_key_path'), str):
                raise ValueError("ssh_key_path in remote_servers must be a string.")
            if not isinstance(server.get('execute_remotely'), bool):
                raise ValueError("execute_remotely in remote_servers must be a boolean.")
            if not isinstance(server.get('steps_to_execute'), list):
                raise ValueError("steps_to_execute in remote_servers must be a list.")

    def get(self, key: str):
        return self.config.get(key)
