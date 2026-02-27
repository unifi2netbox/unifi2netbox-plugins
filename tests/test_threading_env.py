import os
import subprocess
import sys


def _import_sync_engine_with_env(env_overrides):
    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from netbox_unifi_sync.services import sync_engine as m; "
            "print(m.MAX_CONTROLLER_THREADS, m.MAX_SITE_THREADS, m.MAX_DEVICE_THREADS)",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_invalid_thread_env_values_fall_back_to_defaults():
    result = _import_sync_engine_with_env(
        {
            "MAX_CONTROLLER_THREADS": "abc",
            "MAX_SITE_THREADS": "not-a-number",
            "MAX_DEVICE_THREADS": "",
        }
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("5 8 8")


def test_non_positive_thread_env_values_fall_back_to_defaults():
    result = _import_sync_engine_with_env(
        {
            "MAX_CONTROLLER_THREADS": "0",
            "MAX_SITE_THREADS": "-1",
            "MAX_DEVICE_THREADS": "0",
        }
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("5 8 8")
