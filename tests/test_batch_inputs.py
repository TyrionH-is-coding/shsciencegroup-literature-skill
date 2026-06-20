import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "literature_base_upload.py"
TEMP_ROOT = ROOT / ".tmp"
spec = importlib.util.spec_from_file_location("literature_base_upload", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class BatchInputTests(unittest.TestCase):
    def test_collect_pdf_paths_from_directory_and_explicit_paths_dedupes(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            first = root / "a.pdf"
            second = root / "b.PDF"
            nested_dir = root / "nested"
            nested_dir.mkdir()
            nested = nested_dir / "c.pdf"
            text = root / "ignore.txt"
            for path in (first, second, nested, text):
                path.write_bytes(b"x")

            result = mod.collect_pdf_paths([str(root)], [str(first)], recursive=False)

            self.assertEqual(result, [first.resolve(), second.resolve()])

    def test_collect_pdf_paths_recursive_includes_nested_pdfs(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp)
            nested_dir = root / "nested"
            nested_dir.mkdir()
            first = root / "a.pdf"
            nested = nested_dir / "c.pdf"
            for path in (first, nested):
                path.write_bytes(b"x")

            result = mod.collect_pdf_paths([str(root)], [], recursive=True)

            self.assertEqual(result, [first.resolve(), nested.resolve()])


if __name__ == "__main__":
    unittest.main()

