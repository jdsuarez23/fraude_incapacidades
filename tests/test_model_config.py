import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fraude_incapacidades.model_config import get_openai_model
from fraude_incapacidades.tools.ocr_tool import PDFForensicExtractTool


class ModelConfigTests(unittest.TestCase):
    def test_default_and_configured_model(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_openai_model(), "gpt-4o")
        with patch.dict(os.environ, {"OPENAI_MODEL": " custom-model "}):
            self.assertEqual(get_openai_model(), "custom-model")

    def test_empty_model_is_rejected(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "  "}):
            with self.assertRaisesRegex(ValueError, "OPENAI_MODEL"):
                get_openai_model()

    def test_agents_use_configured_model(self):
        with patch.dict(os.environ, {"OPENAI_MODEL": "custom-model", "OPENAI_API_KEY": "test-key"}):
            with patch("dotenv.load_dotenv"):
                crew_module = importlib.import_module("fraude_incapacidades.crew")
                with patch.object(crew_module, "LLM") as llm, patch.object(crew_module, "Agent"):
                    crew_module._build_agents(crew_module.agents_cfg)
                    llm.assert_called_once_with(model="custom-model", api_key="test-key")

    def test_visual_extraction_uses_configured_model(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])
        client = MagicMock()
        client.chat.completions.create.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            path.write_bytes(b"synthetic-image")
            with patch.dict(os.environ, {"OPENAI_MODEL": "custom-model", "OPENAI_API_KEY": "test-key"}):
                with patch("fraude_incapacidades.tools.ocr_tool.openai.OpenAI", return_value=client):
                    result = json.loads(PDFForensicExtractTool()._run(str(path)))
        self.assertIn("datos_estructurados", result)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "custom-model")


if __name__ == "__main__":
    unittest.main()
