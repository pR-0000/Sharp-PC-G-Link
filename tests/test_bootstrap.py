"""Launcher decisions must not install packages or open hardware during tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sharp_link import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_ready_python_and_frozen_release_skip_setup(self):
        with patch.object(bootstrap, 'runtime_ready', return_value=True), patch('subprocess.Popen') as spawn:
            self.assertTrue(bootstrap.ensure_runtime(Path('Sharp PC-G Link.pyw')))
            spawn.assert_not_called()
        with patch.object(bootstrap.sys, 'frozen', True, create=True), patch.object(bootstrap, 'runtime_ready') as ready:
            self.assertTrue(bootstrap.ensure_runtime(Path('Sharp PC-G Link.pyw')))
            ready.assert_not_called()

    def test_existing_local_runtime_relaunches_same_entry_and_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); python = bootstrap.local_python(root)
            python.parent.mkdir(parents=True); python.touch()
            launcher = root / 'Sharp PC-G Link.pyw'
            with patch.object(bootstrap, 'runtime_ready', return_value=False), \
                    patch.object(bootstrap.subprocess, 'run') as probe, \
                    patch.object(bootstrap, 'launch_source') as launch, \
                    patch.object(bootstrap.sys, 'argv', [str(launcher), '--rom-dump']):
                probe.return_value.returncode = 0
                self.assertFalse(bootstrap.ensure_runtime(launcher))
                launch.assert_called_once_with(python, launcher, ['--rom-dump'])
                self.assertNotIn('pip', probe.call_args.args[0])

    def test_relaunch_uses_argument_list_without_shell_and_preserves_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'folder with spaces'; root.mkdir()
            python = root / 'python.exe'; windowed = root / 'pythonw.exe'; windowed.touch()
            launcher = root / 'Sharp PC-G Link.pyw'
            with patch.object(bootstrap.os, 'name', 'nt'), patch.object(bootstrap.subprocess, 'Popen') as spawn:
                bootstrap.launch_source(python, launcher, ['--rom-dump'])
                self.assertEqual(spawn.call_args.args[0], [str(windowed), str(launcher), '--rom-dump'])
                self.assertNotIn('shell', spawn.call_args.kwargs)


if __name__ == '__main__':unittest.main()
