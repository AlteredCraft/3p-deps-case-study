"""Contract of the dev-time ``.env`` loader.

``run.py`` reads a local ``.env`` file before creating the app. That loader is
dev-only tooling (it never runs in production), so its observable boundary is
``os.environ`` rather than HTTP: these tests pin the file format each variant
must honor via the ``load_env`` adapter fixture in conftest. The fixture owns
the environment snapshot/restore.
"""
from __future__ import annotations

import os


def test_env_file_sets_missing_variables(tmp_path, load_env):
    env_file = tmp_path / ".env"
    env_file.write_text("AC_TEST_ALPHA=one\nAC_TEST_BETA=two\n")
    load_env(env_file)
    assert os.environ["AC_TEST_ALPHA"] == "one"
    assert os.environ["AC_TEST_BETA"] == "two"


def test_existing_environment_wins_over_env_file(tmp_path, load_env):
    os.environ["AC_TEST_ALPHA"] = "from-environment"
    env_file = tmp_path / ".env"
    env_file.write_text("AC_TEST_ALPHA=from-file\n")
    load_env(env_file)
    assert os.environ["AC_TEST_ALPHA"] == "from-environment"


def test_comments_blanks_quotes_and_export_prefix(tmp_path, load_env):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment lines are ignored\n"
        "\n"
        'AC_TEST_QUOTED="quoted value"\n'
        "export AC_TEST_EXPORTED=exported\n"
    )
    load_env(env_file)
    assert os.environ["AC_TEST_QUOTED"] == "quoted value"
    assert os.environ["AC_TEST_EXPORTED"] == "exported"


def test_missing_env_file_is_a_no_op(tmp_path, load_env):
    load_env(tmp_path / "does-not-exist.env")
    assert "AC_TEST_ALPHA" not in os.environ
