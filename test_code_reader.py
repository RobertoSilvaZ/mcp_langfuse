import os
import tempfile
import unittest
from pathlib import Path
import code_reader


class CodeReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        code_reader.ROOT = self.root
        (self.root / "main.py").write_text("def hello():\n    return 'world'\n")
        (self.root / ".env").write_text("SECRET=private\n")
        (self.root / "notes.md").write_text("# Changes\nhello world\n")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("secret\n")

    def test_list_and_search(self):
        files = code_reader.list_project_files()["files"]
        self.assertEqual(files, ["main.py", "notes.md"])
        self.assertEqual(code_reader.search_in_code("hello")["matches"][0]["path"], "main.py")

    def test_read_file_lines(self):
        result = code_reader.read_source_file("main.py", max_lines=1)
        self.assertEqual(result["content"], "1: def hello():")

    def test_block_sensitive_and_traversal(self):
        for path in (".env", ".git/config", "../outside.py", "/etc/passwd"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                code_reader.read_source_file(path)

    def test_block_symlinks(self):
        outside = self.root.parent / "outside-source-test.py"
        try:
            (self.root / "linked.py").symlink_to(outside)
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ValueError):
            code_reader.read_source_file("linked.py")


if __name__ == "__main__":
    unittest.main()
