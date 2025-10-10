import os
import stat
import time
import socket
import logging
from datetime import datetime
import paramiko
import pdb

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BRCMDataCollector:
    def __init__(self, host, user, remote_dir, local_dir, qfx_switch, root_passwd, longevity_dir, scenario, check_point, base_dir=None):
        self.host = host
        self.user = user
        self.remote_dir = remote_dir
        self.local_dir = local_dir
        self.qfx_switch = qfx_switch
        self.root_passwd = root_passwd
        self.longevity_dir = longevity_dir
        self.scenario = scenario
        self.check_point = check_point
        self.brcm_base_dir = base_dir
        self.client = self.ssh_connect()
        self.brcm_snapshot = {}
        self.container_id = ''

    def ssh_connect(self):
        for attempt in range(3):
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=self.host,
                    username=self.user,
                    password=self.root_passwd,
                    timeout=10,
                    allow_agent=False,
                    look_for_keys=False
                )
                logging.info(f"SSH connection established to {self.host}")
                return client
            except paramiko.AuthenticationException:
                logging.error(f"Authentication failed for {self.host}. Check your username or password.")
                break
            except (paramiko.SSHException, socket.error, EOFError) as e:
                logging.warning(f"Attempt {attempt+1}: SSH connection error: {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"Unexpected error during SSH connection: {e}")
                break
        raise RuntimeError("Failed to establish SSH connection after multiple attempts")

    def ssh_execute(self, command, workdir=None, get_pty=False):
        for attempt in range(3):
            try:
                if workdir:
                    command = f"cd {workdir} && {command}"

                logging.info(f"🔹 Executing command: {command}")
                stdin, stdout, stderr = self.client.exec_command(command, get_pty=get_pty)

                try:
                    stdout_output = stdout.read().decode(errors="ignore").strip()
                    stderr_output = stderr.read().decode(errors="ignore").strip()
                except (socket.error, EOFError) as e:
                    logging.error(f"⚠️ Socket error while reading output: {e}")
                    return None

                logging.info(f"📝 STDOUT Output: {repr(stdout_output)}")
                if stderr_output and not stdout_output:
                    logging.warning(f"⚠️ STDERR without STDOUT for command [{command}]: {stderr_output}")
                    return None

                return stdout_output if stdout_output else None

            except (paramiko.SSHException, socket.error, EOFError) as e:
                logging.warning(f"Attempt {attempt+1}: SSH error while executing command [{command}]: {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"❌ Unexpected error during SSH command [{command}]: {e}")
                break
        return None

    def run_batchcli(self):
        logging.info("Running batchcli in Docker...")
        for attempt in range(3):
            try:
                cmd = "bash -c 'cd /root/brcm && docker compose run -d batchcli'"
                self.container_id = self.ssh_execute(cmd)
                if self.container_id:
                    self.ssh_execute(f"docker exec {self.container_id.strip()} ls /brcm-batch-cli/cli/")
                    break
            except Exception as e:
                logging.warning(f"Attempt {attempt+1}: Failed to run batchcli: {e}")
                time.sleep(2 ** attempt)

    def create_directories_and_snapshot(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not self.container_id:
            raise RuntimeError("Container ID is not set. Cannot execute snapshot command.")

        base_dir = f"{self.remote_dir}/longevity_{timestamp}"
        logging.info(f"Creating directories and taking initial snapshots in {base_dir}")

        if self.check_point in ['lrm_config_pre_test', 'test_config_pre_test']:
            pre_snapshot_dir = f"{base_dir}/{self.scenario}/{self.check_point}_brcm_baseline"
            self.brcm_snapshot = pre_snapshot_dir
            self.ssh_execute(f"docker exec {self.container_id.strip()} mkdir -p {pre_snapshot_dir}")

            snapshot_cmd = (
                f"docker exec -u root -w /brcm-batch-cli/cli/batch_cli_take_snapshot.runfiles/__main__/brcm-batch-cli/cli "
                f"{self.container_id} /brcm-batch-cli/cli/batch_cli_take_snapshot.runfiles/.batch_cli_take_snapshot.venv/bin/python3 "
                f"take_snapshot_of_brcm_tables.py take-first-snapshot "
                f"--qfx-switch-fqdn {self.qfx_switch} --root-passwd {self.root_passwd} "
                f"--folder-to-host-snapshot {pre_snapshot_dir} --show-prompt"
            )

            logging.info(f"Executing command: {snapshot_cmd}")
            snapshot_output = self.ssh_execute(snapshot_cmd)
            logging.info(f"Snapshot command output: {snapshot_output}")

            if self.verify_snapshot_success(snap_dir=pre_snapshot_dir):
                print("✅ Snapshot executed successfully!")
                return pre_snapshot_dir
            else:
                print("❌ Snapshot failed or insufficient files created.")
                return None

        if self.check_point in ['lrm_config_post_test', 'test_config_post_test']:
            post_snapshot_dir = f"{base_dir}/{self.scenario}/{self.check_point}_brcm_snapshot"
            pre_snapshot_dir = self.brcm_base_dir
            self.brcm_snapshot = post_snapshot_dir
            self.ssh_execute(f"mkdir -p {post_snapshot_dir}")

            snapshot_cmd = (
                f"docker exec -u root -w /brcm-batch-cli/cli/batch_cli_take_snapshot.runfiles/__main__/brcm-batch-cli/cli "
                f"{self.container_id} /brcm-batch-cli/cli/batch_cli_take_snapshot.runfiles/.batch_cli_take_snapshot.venv/bin/python3 "
                f"take_snapshot_of_brcm_tables.py take-next-snapshot-and-do-diff "
                f"--folder-to-host-next-snapshot {post_snapshot_dir} "
                f"--previous_snapshot_location {pre_snapshot_dir} "
                f"--qfx-switch-fqdn {self.qfx_switch} --root-passwd {self.root_passwd} --show-prompt"
            )

            logging.info(f"Executing command: {snapshot_cmd}")
            snapshot_output = self.ssh_execute(snapshot_cmd)
            logging.info(f"Snapshot command output: {snapshot_output}")

            if self.verify_snapshot_success(snap_dir=post_snapshot_dir):
                print("✅ Snapshot executed successfully!")
                return post_snapshot_dir
            else:
                print("❌ Snapshot failed or insufficient files created.")
                return None

    def transfer_logs_to_local(self):
        local_brcm_dir = f"{self.longevity_dir}/brcmsnapshot"
        os.makedirs(local_brcm_dir, exist_ok=True)

        logging.info(f"Connecting to {self.host} for SFTP transfer.")

        for attempt in range(3):
            try:
                transport = self.client.get_transport()
                sftp = paramiko.SFTPClient.from_transport(transport)

                remote_dir = self.brcm_snapshot
                local_dir = os.path.join(local_brcm_dir, os.path.basename(remote_dir))
                os.makedirs(local_dir, exist_ok=True)

                def sftp_recursive_download(remote_path, local_path):
                    for item in sftp.listdir_attr(remote_path):
                        remote_item_path = f"{remote_path}/{item.filename}"
                        local_item_path = os.path.join(local_path, item.filename)

                        if stat.S_ISDIR(item.st_mode):
                            os.makedirs(local_item_path, exist_ok=True)
                            sftp_recursive_download(remote_item_path, local_item_path)
                        else:
                            logging.info(f"Downloading {remote_item_path} → {local_item_path}")
                            try:
                                sftp.get(remote_item_path, local_item_path)
                            except Exception as e:
                                logging.warning(f"⚠️ Failed to download file {remote_item_path}: {e}")

                sftp_recursive_download(remote_dir, local_dir)
                sftp.close()
                logging.info("Log transfer completed successfully.")
                break

            except (socket.error, EOFError) as e:
                logging.warning(f"Attempt {attempt+1}: Socket error during SFTP: {e}")
                time.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"Failed to transfer logs via SFTP: {str(e)}")
                break

    def docker_cleanup(self):
        if self.container_id:
            try:
                self.ssh_execute(f"docker stop {self.container_id.strip()} && docker rm {self.container_id.strip()}")
                logging.info("Container stopped and removed successfully.")
            except Exception as e:
                logging.warning(f"Failed to cleanup Docker container: {e}")

    def execute(self):
        snapshot_dir = None
        try:
            self.run_batchcli()
            snapshot_dir = self.create_directories_and_snapshot()
            self.transfer_logs_to_local()
        except Exception as e:
            logging.error(f"Execution failed: {e}")
        finally:
            try:
                self.docker_cleanup()
                self.client.close()
                logging.info("SSH connection closed.")
            except Exception as e:
                logging.warning(f"Cleanup encountered an error: {e}")
        return snapshot_dir

    def verify_snapshot_success(self, snap_dir):
        logical_folder = f"{snap_dir}/logical"
        check_folder_cmd = f"[ -d {logical_folder} ] && echo 'exists' || echo 'not_found'"
        folder_check = self.ssh_execute(check_folder_cmd)

        if folder_check and 'exists' in folder_check:
            logging.info(f"✅ Logical folder exists: {logical_folder}")
            count_files_cmd = f"find {logical_folder} -type f | wc -l"
            num_files = self.ssh_execute(count_files_cmd)

            if num_files is not None and num_files.strip().isdigit():
                num_files = int(num_files)
                logging.info(f"✅ Total files in {logical_folder}: {num_files}")

                if num_files > 500:
                    logging.info("✅ Snapshot confirmed successfully with sufficient files.")
                    return True
                else:
                    logging.error(f"❌ Snapshot failed: Only {num_files} files found (expected >500)")
                    return False
            else:
                logging.error(f"❌ Failed to count files in {logical_folder}")
                return False
        else:
            logging.error(f"❌ Logical folder not found: {logical_folder}")
            return False



if __name__ == "__main__":
    collector = BRCMDataCollector(
        host="10.83.6.47",
        user="root",
        remote_dir="/var/log/batch_cli",
        local_dir="/path/to/local/log/dir",
        qfx_switch="stqc-q5240-q01.englab.juniper.net",
        root_passwd="Embe1mpls",
        longevity_dir="/volume/regressions/results/JUNOS/HEAD/mmahadevaswa/longevity/IPCLOS/conversion/converted/logs/",
        scenario="Active_test_scenario1",
        check_point="lrm_config_pre_test"
    )
    collector.execute()

