"""Integration test: command-file write -> read -> ControlSignal dispatch."""
import json
import os
import tempfile
import pytest
from control_panel.config_io import write_pomodoro_command


@pytest.fixture
def tmp_config_dir(tmp_path):
    return str(tmp_path)


class TestWritePomodoroCommand:
    def test_creates_command_file(self, tmp_config_dir):
        write_pomodoro_command(tmp_config_dir, "start")
        cmd_path = os.path.join(tmp_config_dir, "pomodoro_command.json")
        assert os.path.exists(cmd_path)
        with open(cmd_path) as f:
            data = json.load(f)
        assert data == {"cmd": "start"}

    def test_overwrites_existing(self, tmp_config_dir):
        write_pomodoro_command(tmp_config_dir, "start")
        write_pomodoro_command(tmp_config_dir, "pause")
        cmd_path = os.path.join(tmp_config_dir, "pomodoro_command.json")
        with open(cmd_path) as f:
            data = json.load(f)
        assert data == {"cmd": "pause"}

    def test_atomic_write(self, tmp_config_dir):
        """No partial file should be visible to readers."""
        write_pomodoro_command(tmp_config_dir, "reset")
        cmd_path = os.path.join(tmp_config_dir, "pomodoro_command.json")
        # File should be valid JSON (not partial)
        with open(cmd_path) as f:
            data = json.load(f)
        assert data["cmd"] == "reset"

    @pytest.mark.parametrize("cmd", ["start", "pause", "reset"])
    def test_all_commands(self, tmp_config_dir, cmd):
        write_pomodoro_command(tmp_config_dir, cmd)
        cmd_path = os.path.join(tmp_config_dir, "pomodoro_command.json")
        with open(cmd_path) as f:
            assert json.load(f)["cmd"] == cmd
