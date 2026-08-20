import subprocess


def test_cli_help_lists_commands():
    res = subprocess.run(["walkthrough", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "validate" in res.stdout
