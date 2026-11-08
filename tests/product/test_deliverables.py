import subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DeliverablesTests(unittest.TestCase):
    def test_AC28_organizer_files_preserved(self):
        result = subprocess.run(
            [
                "git",
                "diff",
                "--exit-code",
                "HEAD",
                "--",
                "data",
                "labels",
                "evaluation",
                "examples",
                "mock_api",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout[:500])

    def test_AC29_runtime_release_files_present(self):
        for name in (
            "README.md", "LICENSE.md", "NOTICE", "config/openapi.json",
            "config/policies.json", "config/reset-baseline.json", "run_demo.py",
            "web/app.js", "web/demo.js", "web/whatsapp.js", "web/whatsapp.css",
            "web/channel-mockups.js", "web/channel-mockups.css",
        ):
            with self.subTest(path=name):
                self.assertGreater((ROOT / name).stat().st_size, 100)

    def test_release_index_contains_no_private_working_material(self):
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        )
        files = result.stdout.decode().rstrip("\0").split("\0")
        forbidden_roots = {"tasks", ".agents", ".codex", ".claude", "runtime", "outputs"}
        forbidden_names = {"AGENTS.md", "CLAUDE.md", "AGENT_WORKFLOW.md"}
        private_documents = (
            "docs/demo/", "docs/detect-design/", "docs/detect-suggest-design/",
            "docs/suggest-design/", "docs/product-handoff/",
            "docs/legacy-readme.md", "docs/legacy-upstream-readme.md",
            "app/teammate/SOURCE.md",
        )
        for filename in files:
            path = Path(filename)
            with self.subTest(path=filename):
                self.assertNotIn(path.parts[0], forbidden_roots)
                self.assertNotIn(path.name, forbidden_names)
                self.assertNotIn("shared-agents", path.parts)
                self.assertFalse(path.name.lower().startswith("handoff"))
                self.assertFalse(filename.startswith(private_documents))
                if path.name.startswith(".env"):
                    self.assertEqual(filename, ".env.example")
