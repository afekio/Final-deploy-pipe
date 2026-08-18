import os
import json
import logging
import subprocess
from datetime import datetime
from Src.path import OS_DATA_PATH, CONFIG_FILE_PATH
from Src.models import TagModel, InstanceModel, ReservationModel, RootModel

def load_os_data(f_logger: logging.Logger, c_logger: logging.Logger) -> dict:
    try:
        with open(OS_DATA_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        f_logger.error(f" Error: The source file {OS_DATA_PATH} was not found.")
        c_logger.error("Error: Source file missing. Check logs.")
        return None
    except json.JSONDecodeError:
        f_logger.error(f" Error: The file {OS_DATA_PATH} contains invalid JSON.")
        c_logger.error("Error: Source file is corrupt. Check logs.")
        return None

def generate_reservation_model(count: int, base_name: str, os_key: str, type_choice: str, os_data: dict) -> RootModel:
    ami = os_data.get(os_key, "ami-unknown")
    i_type = "t2.micro" if type_choice == "1" else "t2.nano"
    launch_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    instances_list = []
    for i in range(1, count + 1):
        name_val = f"{base_name}-{i}"
        instance = InstanceModel(
            ImageId=ami,
            InstanceType=i_type,
            LaunchTime=launch_time,
            Tags=[
                TagModel(Key="Name", Value=name_val)
            ]
        )
        instances_list.append(instance)
    reservation = ReservationModel(Instances=instances_list)
    return RootModel(Reservations=[reservation])

def save_configuration(data_model: RootModel, f_logger: logging.Logger, c_logger: logging.Logger, count: int):
    config_dir = os.path.dirname(CONFIG_FILE_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            f.write(data_model.model_dump_json(indent=4))
        f_logger.info(f"Successfully created configuration for {count} instances in {CONFIG_FILE_PATH}")
        c_logger.info(f"Success! Configuration saved to {CONFIG_FILE_PATH}.")
    except Exception as e:
        f_logger.error(f"Unexpected System Error during file save: {e}")
        c_logger.error("An unexpected error occurred while saving.")
