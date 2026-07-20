"""_resolve_output_path / _resolve_report_dir — çıktı klasörü kuralları
(bkz. plans/output-folder-rules-brief.md, 2026-07-10).

Kural 1: çıktı klasörü == girdi (veya boş) → <girdi>/ÇIKTI/<göreli>.srt
Kural 2: çıktı ayrı klasör             → <çıktı>/<dosya-adı-uzantısız>/<dosya-adı>.srt

Saf modül-düzeyi helper'lar; App/ağ gerektirmez. Windows yol semantiği (büyük/küçük
harf duyarsız, drive) varsayılır — proje Windows-only."""
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class ResolveOutputPathTest(unittest.TestCase):
    def test_same_in_out_makes_cikti_subfolder(self):
        # Kural 1: girdi==çıktı → <girdi>/ÇIKTI/<dosya>
        p = gui._resolve_output_path("/data/subs", "/data/subs", "/data/subs/film.srt")
        self.assertEqual(p.name, "film.srt")
        self.assertEqual(p.parent.name, "ÇIKTI")
        self.assertEqual(p.parent.parent.name, "subs")

    def test_empty_output_treated_as_same(self):
        # Boş çıktı = girdiyle aynı sayılır → Kural 1
        p = gui._resolve_output_path("/data/subs", "", "/data/subs/film.srt")
        self.assertEqual(p.parent.name, "ÇIKTI")
        self.assertEqual(p.name, "film.srt")

    def test_separate_output_makes_named_subfolder(self):
        # Kural 2: ayrı çıktı → <çıktı>/<dosya-adı>/<dosya>
        p = gui._resolve_output_path("/a", "/b/ÇIKTI", "/a/Film.srt")
        self.assertEqual(p.name, "Film.srt")
        self.assertEqual(p.parent.name, "Film")          # dosya adıyla alt-klasör
        self.assertEqual(p.parent.parent.name, "ÇIKTI")  # seçilen ortak çıktı klasörü

    def test_extension_normalized_to_srt(self):
        # Girdi .vtt/.ass olsa da çıktı daima .srt; alt-klasör stem'i uzantısız
        for ext in (".vtt", ".ass", ".srt"):
            p = gui._resolve_output_path("/a", "/b", f"/a/Film{ext}")
            self.assertEqual(p.suffix, ".srt")
            self.assertEqual(p.name, "Film.srt")
            self.assertEqual(p.parent.name, "Film")

    def test_multi_dot_filename_stem_and_subfolder(self):
        # "Film.English(US).vtt" → stem "Film.English(US)" alt-klasör, çıktı .srt
        p = gui._resolve_output_path("/a", "/b", "/a/Film.English(US).vtt")
        self.assertEqual(p.parent.name, "Film.English(US)")
        self.assertEqual(p.name, "Film.English(US).srt")

    def test_recursive_input_preserves_substructure_rule1(self):
        # Kural 1 recursive girdide göreli substructure'ı korur
        p = gui._resolve_output_path("/x", "/x", "/x/sub/dir/f.srt")
        self.assertEqual(p.name, "f.srt")
        self.assertEqual(p.parent.name, "dir")
        self.assertEqual(p.parent.parent.name, "sub")
        self.assertEqual(p.parent.parent.parent.name, "ÇIKTI")

    def test_case_insensitive_same_dir(self):
        # Windows: /X ve /x aynı yer → Kural 1
        p = gui._resolve_output_path("/X", "/x", "/X/f.srt")
        self.assertEqual(p.parent.name, "ÇIKTI")

    def test_filepath_outside_input_dir_fallback(self):
        # relative_to başarısız (dosya girdi klasörü dışında) → dosya adına düşer
        p = gui._resolve_output_path("/x", "/x", "/other/place/f.srt")
        self.assertEqual(p.name, "f.srt")
        self.assertEqual(p.parent.name, "ÇIKTI")
        self.assertEqual(p.parent.parent.name, "x")


class SameFolderModeTest(unittest.TestCase):
    """same_folder=True — Giriş/Çıkış klasörü alanları YOK SAYILIR, çıktı
    dosyanın KENDİ geldiği klasöre kaynak adıyla yazılır (2026-07-20:
    3-4 ayrı klasörden dosya eklenip tek seferde çevrildiğinde her biri
    kendi klasörüne geri dönsün diye eklendi)."""

    def test_ignores_input_output_dir_fields(self):
        # input_dir/output_dir dolu ve BİRBİRİNDEN FARKLI olsa bile yok sayılır
        p = gui._resolve_output_path("/completely/unrelated/input",
                                      "/completely/unrelated/output",
                                      "/data/folderA/film.vtt", same_folder=True)
        self.assertEqual(p.parent, Path("/data/folderA"))
        self.assertEqual(p.name, "film.srt")

    def test_different_files_each_return_to_own_folder(self):
        # 3 ayrı klasörden eklenen dosyalar kendi klasörlerine gider
        for folder in ("/x/A", "/y/B", "/z/C/deep"):
            p = gui._resolve_output_path("", "", f"{folder}/ep.srt", same_folder=True)
            self.assertEqual(str(p.parent).replace("\\", "/"), folder)

    def test_srt_source_collision_falls_back_to_tr_srt(self):
        # Kaynak zaten .srt ise hesaplanan yol kaynakla BİREBİR çakışır;
        # orijinali silmemek için <isim>.tr.srt kullanılır.
        p = gui._resolve_output_path("", "", "/data/subs/film.srt", same_folder=True)
        self.assertEqual(p.parent, Path("/data/subs"))
        self.assertEqual(p.name, "film.tr.srt")
        self.assertNotEqual(str(p), str(Path("/data/subs/film.srt")))

    def test_non_srt_source_no_collision_no_suffix(self):
        # .vtt/.ass kaynaklarda uzantı zaten değiştiği için çakışma yok — düz isim
        for ext in (".vtt", ".ass"):
            p = gui._resolve_output_path("", "", f"/data/subs/film{ext}", same_folder=True)
            self.assertEqual(p.name, "film.srt")


class Rule1ReachableTest(unittest.TestCase):
    """Kural 1 GERÇEKTEN ulaşılabilir olmalı.

    2026-07-17'de fark edildi: `_start()` içinde "Çıkış klasörü giriş klasörüyle aynı
    olamaz — kaynak dosyaların üzerine yazılır" diye SERT bir engel vardı; yani girdi==çıktı
    yapılandırması çeviriyi hiç başlatamıyordu ve Kural 1 ÖLÜ KODdu (kullanıcının açık
    isteği olmasına rağmen). Engelin gerekçesi zaten Kural 1 ile geçersizleşmişti
    (artık kaynağın yanına değil, <girdi>/ÇIKTI/ içine yazılıyor). Engel kaldırıldı;
    bu test geri gelirse yakalar."""

    def test_start_has_no_same_dir_block(self):
        src = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Çıkış klasörü giriş klasörüyle aynı olamaz", src,
                         "girdi==çıktı engeli geri gelmiş — Kural 1 yine ölü kod olur")

    def test_same_dir_routes_into_cikti_not_over_source(self):
        # Engelin KORKTUĞU şey (kaynağın üzerine yazma) artık gerçekleşemiyor:
        # çıktı kaynağın yanına değil, ÇIKTI alt-klasörüne gidiyor.
        src_file = "/data/subs/film.srt"
        out = gui._resolve_output_path("/data/subs", "/data/subs", src_file)
        self.assertNotEqual(str(out).replace("\\", "/").lower(), src_file.lower())
        self.assertEqual(out.parent.name, "ÇIKTI")


class PathsEqualTest(unittest.TestCase):
    def test_equal_and_unequal(self):
        self.assertTrue(gui._paths_equal("/data/x", "/data/x"))
        self.assertFalse(gui._paths_equal("/data/x", "/data/y"))

    def test_empty_never_equal(self):
        self.assertFalse(gui._paths_equal("", "/data/x"))
        self.assertFalse(gui._paths_equal("/data/x", ""))
        self.assertFalse(gui._paths_equal("", ""))

    def test_trailing_slash_and_case_insensitive(self):
        # Windows: sondaki ayraç ve harf büyüklüğü fark etmez
        self.assertTrue(gui._paths_equal("/data/X\\", "/data/x"))


class ResolveReportDirTest(unittest.TestCase):
    def test_same_dir_report_goes_into_cikti(self):
        d = gui._resolve_report_dir("/data/subs", "/data/subs")
        self.assertEqual(d.name, "ÇIKTI")
        self.assertEqual(d.parent.name, "subs")

    def test_empty_output_report_goes_into_cikti(self):
        d = gui._resolve_report_dir("/data/subs", "")
        self.assertEqual(d.name, "ÇIKTI")

    def test_separate_output_report_stays_at_root(self):
        # Kural 2: rapor çıktı KÖKÜNDE (dosya alt-klasörlerinin üstünde)
        d = gui._resolve_report_dir("/a", "/b/ÇIKTI")
        self.assertEqual(d.name, "ÇIKTI")
        self.assertEqual(d.parent.name, "b")


if __name__ == "__main__":
    unittest.main()
