import os
import paramiko
from typing import Tuple, Optional, Dict, Any
import logging

class SSHManager:
    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.logger = logging.getLogger('PipelineLogger')

    def establish_connection(self) -> bool:
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if self.server_config.get('ssh_key_path'):
                key_path = self.server_config['ssh_key_path']
                if not os.path.exists(key_path):
                    self.logger.error(f"SSH key path does not exist: {key_path}")
                    return False
                key = paramiko.RSAKey.from_private_key_file(key_path)
                self.ssh_client.connect(
                    hostname=self.server_config['hostname'],
                    port=self.server_config.get('port', 22),
                    username=self.server_config['username'],
                    pkey=key,
                    timeout=10
                )
            else:
                self.ssh_client.connect(
                    hostname=self.server_config['hostname'],
                    port=self.server_config.get('port', 22),
                    username=self.server_config['username'],
                    password=self.server_config.get('password'),
                    timeout=10
                )
            self.logger.info(f"Successfully connected to {self.server_config['hostname']}")
            return True
        except paramiko.AuthenticationException:
            self.logger.error("Authentication failed when connecting to %s", self.server_config['hostname'])
        except paramiko.SSHException as sshException:
            self.logger.error("Unable to establish SSH connection: %s", sshException)
        except Exception as e:
            self.logger.error("Exception in establishing SSH connection: %s", e)
        return False

    def execute_command(self, command: str) -> Tuple[str, str]:
        if not self.ssh_client:
            self.logger.error("SSH client not connected.")
            return "", "SSH client not connected."
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            out = stdout.read().decode()
            err = stderr.read().decode()
            if err:
                self.logger.error("Error executing command '%s': %s", command, err)
            else:
                self.logger.info("Successfully executed command: %s", command)
            return out, err
        except paramiko.SSHException as sshException:
            self.logger.error("Failed to execute command '%s': %s", command, sshException)
            return "", str(sshException)
        except Exception as e:
            self.logger.error("Exception during command execution: %s", e)
            return "", str(e)

    def transfer_file(self, local_path: str, remote_path: str) -> bool:
        if not self.ssh_client:
            self.logger.error("SSH client not connected.")
            return False
        try:
            sftp = self.ssh_client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            self.logger.info(f"Successfully transferred {local_path} to {remote_path}")
            return True
        except FileNotFoundError:
            self.logger.error("Local file not found: %s", local_path)
        except paramiko.SSHException as sshException:
            self.logger.error("SFTP transfer failed: %s", sshException)
        except Exception as e:
            self.logger.error("Exception during file transfer: %s", e)
        return False

    def close_connection(self):
        if self.ssh_client:
            self.ssh_client.close()
            self.logger.info(f"SSH connection to {self.server_config['hostname']} closed.")
