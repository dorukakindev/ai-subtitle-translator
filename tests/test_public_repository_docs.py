"""Offline checks for the public repository documentation contract."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicRepositoryDocsTest(unittest.TestCase):
    def test_required_public_files_exist(self):
        for relative in (
            "README.md",
            "README.tr.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
            "PRIVACY.md",
            "SECURITY.md",
            "Architecture.md",
            ".github/workflows/tests.yml",
            ".github/ISSUE_TEMPLATE/bug.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_local_readme_links_resolve(self):
        for name in ("README.md", "README.tr.md"):
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
                if "://" in target or target.startswith("#"):
                    continue
                local = target.split("#", 1)[0]
                with self.subTest(readme=name, target=target):
                    self.assertTrue((ROOT / local).exists())

    def test_credentials_are_not_described_as_encrypted(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8-sig").lower()
        turkish = (ROOT / "README.tr.md").read_text(encoding="utf-8-sig").lower()
        privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8-sig").lower()
        self.assertIn("obfus", english)
        self.assertIn("karart", turkish)
        self.assertIn("obfus", privacy)
        self.assertNotIn("encrypted fallback", english)

    def test_public_tree_excludes_internal_working_material(self):
        # Çalışma ağacında yerel dizinler (ör. plans/ denetim raporları,
        # YENİDEN ÇEVRİLECEK/ kullanıcı kuyruğu) meşru olarak bulunabilir;
        # sözleşme bunların depoya GİRMEMESİ — tracked liste denetlenir,
        # git yoksa dışa aktarılmış ağaçta fiziksel varlığa düşülür.
        tracked = None
        try:
            import subprocess
            listing = subprocess.run(
                ["git", "ls-files"], cwd=ROOT, capture_output=True,
                text=True, check=True, timeout=30)
            tracked = {line.strip() for line in listing.stdout.splitlines()
                       if line.strip()}
        except Exception:
            pass
        for relative in (
            "AGENTS.md",
            "CLAUDE.md",
            "plans",
            "HARİÇ TUTULANLAR",
            "YENİDEN ÇEVRİLECEK",
        ):
            with self.subTest(relative=relative):
                if tracked is None:
                    self.assertFalse((ROOT / relative).exists())
                else:
                    self.assertFalse(any(
                        path == relative or path.startswith(relative + "/")
                        for path in tracked))

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
