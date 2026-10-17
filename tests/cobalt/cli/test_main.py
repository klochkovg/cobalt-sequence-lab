import subprocess
import sys

from cobalt.cli.main import EXIT_BROKEN_PIPE


def test_closed_stdout_exits_quietly(tmp_path):
    # Enough rows to overflow the pipe buffer after the reader goes away
    fasta = tmp_path / "many.fasta"
    fasta.write_text("".join(f">s{i}\nACGTACGT\n" for i in range(5000)))

    proc = subprocess.Popen(
        [sys.executable, "-m", "cobalt", "stats", str(fasta)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None and proc.stderr is not None
    assert proc.stdout.readline().startswith(b"id,")
    proc.stdout.close()  # like `| head -1`
    stderr = proc.stderr.read().decode()
    proc.stderr.close()

    assert proc.wait(timeout=30) == EXIT_BROKEN_PIPE
    assert "Traceback" not in stderr
    assert "BrokenPipeError" not in stderr
