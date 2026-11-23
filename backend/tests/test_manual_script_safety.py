"""Manual checks must not run during pytest collection or module inspection."""
from pathlib import Path
import runpy
import pytest


@pytest.mark.parametrize('name', ['test_tts.py', 'test_storage.py'])
def test_manual_check_import_has_no_side_effects(name, capsys):
    namespace = runpy.run_path(str(Path(__file__).parents[1] / name))
    assert callable(namespace['main'])
    assert capsys.readouterr().out == ''
