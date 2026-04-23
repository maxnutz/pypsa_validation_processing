from pathlib import Path
import tomllib


def test_workflow_test_task_runs_all_required_commands_in_order():
    pixi_toml_path = Path(__file__).resolve().parent.parent / "pixi.toml"
    pixi_config = tomllib.loads(pixi_toml_path.read_text())

    task_command = pixi_config["tasks"]["workflow_test"]
    parts = task_command.split(" && ")

    assert parts == [
        "python workflow.py --config pypsa_validation_processing/configs/config.country-timeseries.yaml",
        "python workflow.py --config pypsa_validation_processing/configs/config.country-year.yaml",
        "python workflow.py --config pypsa_validation_processing/configs/config.region-timeseries.yaml",
        "python workflow.py --config pypsa_validation_processing/configs/config.region-year.yaml",
        "pytest tests/ -v",
    ]
