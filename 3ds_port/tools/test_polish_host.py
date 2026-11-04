"""Run the narrow, hardware-independent display and input contracts."""
import subprocess
import tempfile
from pathlib import Path

port = Path(__file__).resolve().parents[1]
tests = ('lower_auto_test.c', 'lower_policy_test.c', 'game_screen_test.c', 'ambient_display_test.c',
         'stage10_modern_controls_test.c')
with tempfile.TemporaryDirectory(prefix='sh-polish-host-') as name:
    for filename in tests:
        binary = Path(name) / filename.removesuffix('.c')
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(port / 'include'), str(port / 'tests' / filename),
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
