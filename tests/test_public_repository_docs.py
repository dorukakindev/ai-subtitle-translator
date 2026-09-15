"""Public depo belgeleri ve kurulum sözleşmesi için çevrimdışı kontroller."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicRepositoryDocsTest(unittest.TestCase):
    def test_required_public_files_exist(self):
        for relative in (
            "README.md",
            "README.en.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "PRIVACY.md",
            "SECURITY.md",
            "PUBLIC_RELEASE_CHECKLIST.md",
            ".github/workflows/tests.yml",
            ".github/ISSUE_TEMPLATE/bug.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_local_readme_links_resolve(self):
        for name in ("README.md", "README.en.md"):
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                with self.subTest(readme=name, target=target):
                    self.assertTrue((ROOT / local).exists())

    def test_credentials_are_not_described_as_encrypted(self):
        for name in ("README.md", "README.en.md", "PRIVACY.md"):
            text = (ROOT / name).read_text(encoding="utf-8-sig").lower()
            self.assertNotIn("şifrelenmiş bir yedek", text)
            self.assertNotIn("encrypted fallback", text)
            marker = "obfus" if name == "README.en.md" else "karart"
            self.assertIn(marker, text)

    def test_drag_drop_is_installed_during_setup_not_launch(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8-sig")
        launcher = (ROOT / "Başlat.bat").read_text(encoding="utf-8-sig")
        self.assertRegex(requirements, r"(?m)^tkinterdnd2>=")
        self.assertNotIn("-m pip install tkinterdnd2", launcher)
        self.assertIn("pip install -r requirements.txt", launcher)

    def test_runtime_and_personal_files_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
        for pattern in (
            "active_run.*.json.lock",
            "girdi_style_glossary.txt",
            "ÇEVRİLEN FİLMLER.pre-*.txt.bak",
            "Raporlar/",
        ):
            self.assertIn(pattern, ignore)


if __name__ == "__main__":
    unittest.main()
