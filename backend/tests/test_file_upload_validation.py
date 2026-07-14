"""
Tests for upload file validation.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

sys.modules.setdefault("graph", types.SimpleNamespace(agent_manager=object()))
skills_scanner = types.ModuleType("tools.skills_scanner")
skills_scanner.scan_skills = lambda skills_dir: []
tools_package = types.ModuleType("tools")
tools_package.__path__ = [str(BACKEND_DIR / "tools")]
sys.modules.setdefault("tools", tools_package)
sys.modules["tools.skills_scanner"] = skills_scanner


class NoOpRouter:
    def get(self, *args, **kwargs):
        return lambda func: func

    def post(self, *args, **kwargs):
        return lambda func: func

fastapi = types.ModuleType("fastapi")
fastapi.APIRouter = NoOpRouter
fastapi.HTTPException = Exception
fastapi.Query = lambda *args, **kwargs: None
fastapi.UploadFile = object
fastapi.File = lambda *args, **kwargs: None
with patch.dict(sys.modules, {"fastapi": fastapi}):
    spec = importlib.util.spec_from_file_location("files_api", BACKEND_DIR / "api" / "files.py")
    files_api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(files_api)
validate_upload_file = files_api.validate_upload_file
sys.modules.pop("tools.skills_scanner", None)
sys.modules.pop("tools", None)


class UploadFileValidationTest(unittest.TestCase):
    def test_accepts_supported_table_document_extensions(self):
        """CSV and Excel spreadsheet files are accepted for upload."""
        for filename in ("report.csv", "report.xlsx", "report.xls"):
            with self.subTest(filename=filename):
                is_valid, error_message = validate_upload_file(filename, 1024)

                self.assertTrue(is_valid)
                self.assertEqual("", error_message)

    def test_accepts_word_documents(self):
        """Word document files are accepted for upload."""
        for filename in ("proposal.doc", "proposal.docx"):
            with self.subTest(filename=filename):
                is_valid, error_message = validate_upload_file(filename, 1024)

                self.assertTrue(is_valid)
                self.assertEqual("", error_message)

    def test_accepts_files_up_to_200mb(self):
        """Single upload file limit is 200MB."""
        is_valid, error_message = validate_upload_file("large.pdf", 200 * 1024 * 1024)

        self.assertTrue(is_valid)
        self.assertEqual("", error_message)

    def test_rejects_files_over_200mb(self):
        """Files larger than 200MB are rejected."""
        is_valid, error_message = validate_upload_file("too-large.pdf", 200 * 1024 * 1024 + 1)

        self.assertFalse(is_valid)
        self.assertIn("限制: 200MB", error_message)


if __name__ == "__main__":
    unittest.main()
