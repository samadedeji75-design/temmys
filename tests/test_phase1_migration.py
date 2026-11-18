"""Run the real Alembic migrations against fresh SQLite files."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PREVIOUS_HEAD = "a3c91d5e7b20"
NEW_HEAD = "b81d4e6f2c35"


def _flask(db_file, *args):
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": f"sqlite:///{db_file}",
        "FLASK_ENV": "development",
        "FLASK_APP": "wsgi.py",
    })
    return subprocess.run(
        [sys.executable, "-m", "flask", "db", *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )


def _columns(db_file, table):
    con = sqlite3.connect(db_file)
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def _ok(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_upgrade_then_downgrade(tmp_path):
    db_file = tmp_path / "fresh.db"
    _ok(_flask(db_file, "upgrade"))
    assert "section" in _columns(db_file, "class_level")
    assert "class_teacher_id" in _columns(db_file, "class_arm")
    assert "source" in _columns(db_file, "teacher_subject_assignment")

    _ok(_flask(db_file, "downgrade"))
    assert "section" not in _columns(db_file, "class_level")
    assert "class_teacher_id" not in _columns(db_file, "class_arm")
    assert "source" not in _columns(db_file, "teacher_subject_assignment")


def test_upgrade_backfills_defaults(tmp_path):
    db_file = tmp_path / "existing.db"
    _ok(_flask(db_file, "upgrade", PREVIOUS_HEAD))

    con = sqlite3.connect(db_file)
    con.execute('INSERT INTO class_level (name, "order") VALUES ("SS 1", 1)')
    con.execute("INSERT INTO class_arm (name, class_level_id) VALUES ('Gold', 1)")
    con.execute("INSERT INTO teacher (full_name, email, password_hash, is_active) VALUES ('T', 't@x.com', 'h', 1)")
    con.execute("INSERT INTO subject (name) VALUES ('Maths')")
    con.execute("INSERT INTO teacher_subject_assignment (teacher_id, class_arm_id, subject_id) VALUES (1, 1, 1)")
    con.commit()
    con.close()

    _ok(_flask(db_file, "upgrade"))

    con = sqlite3.connect(db_file)
    assert con.execute("SELECT section FROM class_level").fetchone()[0] == "secondary"
    assert con.execute("SELECT class_teacher_id FROM class_arm").fetchone()[0] is None
    assert con.execute("SELECT source FROM teacher_subject_assignment").fetchone()[0] == "manual"
    assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == NEW_HEAD
    con.close()


def test_upgrade_is_safe_if_column_already_exists(tmp_path):
    db_file = tmp_path / "partial.db"
    _ok(_flask(db_file, "upgrade", PREVIOUS_HEAD))
    con = sqlite3.connect(db_file)
    con.execute("ALTER TABLE class_level ADD COLUMN section VARCHAR(20) NOT NULL DEFAULT 'secondary'")
    con.commit()
    con.close()
    _ok(_flask(db_file, "upgrade"))
