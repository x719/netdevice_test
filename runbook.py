from nornir import InitNornir
from nornir_utils.plugins.functions import print_result
from nornir_netmiko import netmiko_send_command
import datetime
import logging
import os


logging.basicConfig(
    level=logging.INFO,
    filename = os.path.join(os.path.dirname(__file__), "backup_log.log"),
    filemode = 'a',
    format='%(asctime)s - %(levelname)s - %(message)s'

)
logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Base class for backup errors"""
    def __init__(self, message: str, device_name: str, error_type: str = "unknown"):
        self.message = message
        self.device_name = device_name
        self.error_type = error_type
        super().__init__(message)


class BackupCommandError(BackupError):
    """execute command error"""
    pass


class BackupConnectionError(BackupError):
    """connection error"""
    pass


def netdevice_start_conf_backup(task):
    """backup device configuration"""
    time = str(datetime.date.today())
    cmd_template = task.host.data['cmd_bak']
    hostname = task.host.name
    cmd = f"{cmd_template} {hostname}_{time}.zip"

    result_data = {
        "device": hostname,
        "status": "failed",
        "command": cmd,
        "output": None,
        "error": None,
        "error_type": None        
    }

    try:
        exec_result =task.run(netmiko_send_command, command_string=cmd)
        output = str(exec_result.result)
        error_keywords = ["error", "failed", "invalid", "exception"]

        if any(key in output for key in error_keywords):
            raise BackupCommandError(
                message=f"Command execution failed for {hostname}",
                device_name=hostname,
                error_type="command_execution"
            )
        
        result_data["status"] = "success"
        result_data["output"] = output
        logger.info(f"Successfully backed up configuration for {hostname}")

    except BackupCommandError as e:
        result_data["error"] = e.message
        result_data["error_type"] = e.error_type
        logger.error(f"Device {e.device_name} - {e.error_type}: {e.message}")

    except Exception as e:
        error_msg = str(e)
        result_data["error"] = error_msg

        if "Timeout" in error_msg:
            result_data["error_type"] = "connection_timeout"
        elif "Authentication" in error_msg:
            result_data["error_type"] = "authentication_failure"
        else:
            result_data["error_type"] = "network_error"

        logger.error(f"Device {hostname} - {result_data['error_type']}: {error_msg}")

    return result_data

def main():
    summary = {
        "total_devices": 0,
        "successful_backups": 0,
        "failed_backups": 0,
        "errors": []
    }

    try:
        logger.info("Initializing Nornir...")
        config_path = os.path.join(os.path.dirname(__file__), "nornir.yaml")
        nr = InitNornir(config_file = config_path)

        summary["total_devices"] = len(nr.inventory.hosts)
        logger.info(f"Total devices to backup: {summary['total_devices']}")

        logger.info("Starting configuration backup tasks...")
        results = nr.run(task=netdevice_start_conf_backup)
        
        for device, result in results.items():
            result_data = result[0].result

            if result_data["status"] == "success":
                summary["successful_backups"] += 1
            else:
                summary["failed_backups"] += 1
                summary["errors"].append({
                    "device": result_data["device"],
                    "error_type": result_data["error_type"],
                    "error_message": result_data["error"]
                })
        logger.info("Backup tasks completed.")
        logger.info(f"Summary: Total devices: {summary['total_devices']}, Successful: {summary['successful_backups']}, Failed: {summary['failed_backups']}")

        print("\n" + "=" * 50)
        print("Backup Summary:")
        print(f"Total devices: {summary['total_devices']}")
        print(f"Successful backups: {summary['successful_backups']}")
        print(f"Failed backups: {summary['failed_backups']}")

        if summary["errors"]:
            print("\nErrors:")
            for error in summary["errors"]:
                print(f"Device: {error['device']}, Error Type: {error['error_type']}, Message: {error['error_message']}")

        print("=" * 50)

        return summary
    
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        raise

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Script execution failed: {e}")
