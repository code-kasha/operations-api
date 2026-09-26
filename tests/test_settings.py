import os
import subprocess
import sys

import pytest


def production_settings(**overrides):
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "SECRET_KEY",
            "ALLOWED_HOSTS",
            "DATABASE_URL",
            "ORGANISATION_SECTOR",
        }
    }
    env.update(
        {
            "SECRET_KEY": "test-only-7ae54cd63898a7c53c430438ed7a645c6447bcad989a112241",
            "ALLOWED_HOSTS": "example.com",
            "DATABASE_URL": "postgresql://fictional:fictional@localhost/operations",
        }
    )
    env.update(overrides)
    return subprocess.run(
        [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
            "--settings=config.settings.production",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_production_settings_pass_deployment_checks():
    result = production_settings()
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SECRET_KEY": ""}, "SECRET_KEY"),
        ({"SECRET_KEY": "x" * 60}, "SECRET_KEY"),
        ({"ALLOWED_HOSTS": ""}, "ALLOWED_HOSTS"),
        ({"ALLOWED_HOSTS": "*"}, "ALLOWED_HOSTS"),
        ({"DATABASE_URL": ""}, "DATABASE_URL"),
        ({"DATABASE_URL": "sqlite:///db.sqlite3"}, "DATABASE_URL"),
        ({"ORGANISATION_SECTOR": "unknown"}, "ORGANISATION_SECTOR"),
    ],
)
def test_production_refuses_misconfiguration(overrides, message):
    result = production_settings(**overrides)
    assert result.returncode != 0
    assert message in result.stderr
