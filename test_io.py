import os
import tempfile
import shutil
import unittest

TEXT_CONTENT = "Hello, Eurocar!\n"
BINARY_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
LARGE_LINE = "A" * 1024
LARGE_CONTENT = (LARGE_LINE + "\n") * 100


class TestFileIO(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eurocar_io_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _path(self, name):
        return os.path.join(self.test_dir, name)

    def test_write_and_read_text(self):
        path = self._path("hello.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(TEXT_CONTENT)
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertEqual(data, TEXT_CONTENT)

    def test_write_and_read_binary(self):
        path = self._path("image.png")
        with open(path, "wb") as f:
            f.write(BINARY_CONTENT)
        with open(path, "rb") as f:
            data = f.read()
        self.assertEqual(data, BINARY_CONTENT)

    def test_file_not_found(self):
        path = self._path("does_not_exist.txt")
        with self.assertRaises(FileNotFoundError):
            open(path, "r")

    def test_overwrite_file(self):
        path = self._path("overwrite.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old content")
        with open(path, "w", encoding="utf-8") as f:
            f.write("new content")
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new content")

    def test_empty_file(self):
        path = self._path("empty.txt")
        open(path, "w").close()
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "")

    def test_append_mode(self):
        path = self._path("append.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("line1\n")
        with open(path, "a", encoding="utf-8") as f:
            f.write("line2\n")
        with open(path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "line1\nline2\n")

    def test_large_content(self):
        path = self._path("large.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(LARGE_CONTENT)
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertEqual(len(data), len(LARGE_CONTENT))
        self.assertEqual(data, LARGE_CONTENT)


if __name__ == "__main__":
    unittest.main()
