"""Runtime localization for user-facing desktop UI text.

The application logic keeps its stable Turkish enum values; this module only
translates presentation strings. English is the first-run interface language.
"""

from __future__ import annotations

import re

UI_LANGUAGES = ("English", "Türkçe")
DEFAULT_UI_LANGUAGE = "English"


def normalize_ui_language(value: object) -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"türkçe", "turkce", "turkish", "tr"}:
        return "Türkçe"
    return DEFAULT_UI_LANGUAGE


# Exact UI copy. Internal enum values (Otomatik, Dizi, Orta, etc.) deliberately
# stay untouched so changing the display language cannot alter translation logic.
EN = {
    "Altyazı Çevirisi": "AI Subtitle Translator",
    "Hazırlık": "Preparation", "Teslim": "Delivery",
    "ÇALIŞIYOR": "RUNNING", "ÇEVİRİYE HAZIR": "READY TO TRANSLATE",
    "Arayüz": "Interface",
    "Bağlamı koruyan çeviri, özenli altyazılar.": "Context-aware translation, carefully crafted subtitles.",
    "+ Dosya ekle": "+ Add files",
    "Klasör ekle": "Add folder",
    "Bağlantı": "Connection", "Çeviri": "Translation", "Dil": "Language",
    "Dosyalar": "Files", "Kalite": "Quality", "Araçlar": "Tools",
    "API AYARLARI": "API SETTINGS", "ÇEVİRİ MODU": "TRANSLATION MODE",
    "DİL": "LANGUAGE", "KLASÖRLER": "FOLDERS", "KALİTE": "QUALITY",
    "ARAÇLAR": "TOOLS", "Bağlam ve parçalama": "Context and chunking",
    "API ve performans": "API and performance",
    "OpenAI API Base URL (opsiyonel)": "OpenAI API Base URL (optional)",
    "Boş bırak: https://api.openai.com/v1": "Leave blank: https://api.openai.com/v1",
    "Ana Model — Özel Sağlayıcı": "Main model — Custom provider",
    "Ana çeviri için ayrı bir sağlayıcı kullanın. Kapatıldığında OpenAI bağlantısı kullanılır.": "Use a separate provider for the main translation. When disabled, the OpenAI connection is used.",
    "Model Adı": "Model name", "Ana çeviri API rotası": "Main translation API route",
    "Özel / seçili API URL (taban adres)": "Custom / selected API URL (base address)",
    "API Anahtarı": "API key", "Model Limit Grubu": "Model limit group",
    "Hafif Modeller (2.5M Limit)": "Light models (2.5M limit)",
    "Zeki Modeller (250K Limit)": "Advanced models (250K limit)",
    "2.5M / Gün": "2.5M / day", "250K / Gün": "250K / day",
    "Kaynak dil": "Source language", "Hedef dil": "Target language",
    "İçerik türü": "Content type", "Yapı türü": "Media type",
    "Argo / Küfür": "Slang / profanity",
    "Aynı Klasöre Kaydet": "Save beside source",
    "📄  Dosya Seç (.srt/.vtt/.ass)": "📄  Select files (.srt/.vtt/.ass)",
    "📂  Klasörler Ekle": "📂  Add folders", "🎞  Videodan Altyazı Ekle": "🎞  Add subtitles from video",
    "Temizle ✕": "Clear ✕", "SDH Temizle": "Remove SDH",
    "[Steve sighs], [woman speaking] gibi\nses açıklama satırlarını çıktıdan siler.": "Removes sound-description lines such as\n[Steve sighs] and [woman speaking] from the output.",
    "Sonrası: LLM incelemesi": "Afterwards: LLM review",
    "Sonrası: Doğrudan teslim": "Afterwards: Direct delivery",
    "Zincirleme Bağlam": "Chained context", "Eksik Cue API Onarımı": "Missing-cue API repair",
    "Ön-Bağlam Analizi": "Pre-context analysis", "Dizi Hafızası": "Series memory",
    "Sezon Sonu Kanon Denetimi": "End-of-season canon review",
    "Bağlam İncelemesi (Batch)": "Context review (Batch)",
    "Terim Normalizasyonu": "Terminology normalization", "└ Düzeltmeleri uygula": "└ Apply corrections",
    "Cue-fill taşıma": "Cue-fill relocation",
    "Teslim + Otomatik Düzeltme: Yalnız Raporla": "Delivery + automatic fixes: Report only",
    "İki-Dalgalı Zincirli Batch": "Two-wave chained Batch",
    "Critic Pass": "Critic pass", "Polish Pass": "Polish pass", "QC Kontrolü": "QC review",
    "🇹🇷 Native Okuyucu": "Native reader", "Geri Çeviri Anlam Kontrolü": "Back-translation meaning check",
    "Nihai Anlam Mutabakatı": "Final semantic reconciliation",
    "Derin Teslim Anlam Taraması": "Deep delivery semantic scan",
    "Ham Çeviri Yedeği (.ham.srt)": "Raw translation backup (.ham.srt)",
    "Auto-Glossary": "Auto glossary", "Satır Kırma": "Line wrapping",
    "Parçalı Cue Birleştir": "Merge fragmented cues", "AI Akıllı Segmentasyon": "AI semantic segmentation",
    "Okuma Hızı Kısaltma": "Reading-speed condensation", "Yardimci Analiz": "Assisted analysis",
    "API'yi Dene": "Test API", "Ana + pass API otomatik rota geçişi": "Automatic API route failover for main + passes",
    "4 Rotayı Karşılaştır": "Compare 4 routes", "ÇALIŞMA HAZIRLIĞI": "RUN PREPARATION",
    "Maliyet tahmini": "Cost estimate", "ÇALIŞMA DAVRANIŞI": "RUN BEHAVIOR",
    "🔔  Masaüstü bildirimi": "🔔  Desktop notification",
    "Canlı ilerleme animasyonları": "Live progress animations",
    "⏻  Bitince bilgisayarı kapat": "⏻  Shut down computer when finished",
    "Çalışırken uyku modunu engelle": "Prevent sleep while running",
    "Başarısız dosyaları otomatik yeniden dene (Anında)": "Automatically retry failed files (Sync)",
    "Çökme sonrası otomatik devam": "Automatically resume after a crash",
    "Tümüne Uygula": "Apply to all", "Oturum günlüğü": "Session log",
    "Alta git": "Go to bottom", "Son özet": "Last summary", "Temizle": "Clear",
    "Kısayollar": "Shortcuts", "Kılavuz": "Guide (Turkish)",
    "DOSYA": "FILES", "SATIR": "CUES", "TAMAMLANAN": "COMPLETED", "HATALI": "FAILED",
    "TM VURUŞ": "TM HITS", "TOKEN": "TOKENS", "Hazır": "Ready",
    "Dosya veya klasör ekleyerek başlayın.": "Start by adding files or a folder.",
    "DOSYA BEKLENİYOR": "WAITING FOR FILES", "Dosya veya klasör ekleyin": "Add files or a folder",
    "▶  Çeviriyi başlat": "▶  Start translation", "API testi": "API test",
    "↺  Batch'i Devam Ettir": "↺  Resume Batch", "📂  JSONL → SRT": "📂  JSONL → SRT",
    "✦  SRT Post-İşle": "✦  Post-process SRT", "📊  Kalite Raporu": "📊  Quality report",
    "⚙️  Gelişmiş Ayarlar": "⚙️  Advanced settings", "🧠  Proje Hafızası": "🧠  Project memory",
    "⏸  Duraklat": "⏸  Pause", "↷  Bu Pass'i Atla": "↷  Skip this pass",
    "↷  Bu Dosyayı Atla": "↷  Skip this file", "■  Durdur": "■  Stop",
    "🔑  API Anahtarları": "🔑  API keys", "Kopyala": "Copy", "Tanı paketi": "Diagnostic bundle",
    "Kapat": "Close", "İptal": "Cancel", "İptal Et": "Cancel", "Devam Et": "Continue",
    "▶  Devam": "▶  Continue", "Şimdi Devam Et": "Resume now", "Tekrar Dene": "Retry",
    "Tekrar Test Et": "Test again", "Bekle": "Wait", "Çalışmayı Durdur": "Stop run",
    "📋 Logları Kopyala": "📋 Copy logs", "🩺 Tanı Paketi": "🩺 Diagnostic bundle",
    "Kullanım Kılavuzu": "User guide", "Klavye Kısayolları": "Keyboard shortcuts",
    "Ara: ayar adı ya da geçen bir söz…": "Search settings or text…",
    "Yarım Kalan Çalışma": "Interrupted run", "⏳  Yarım Kalan Batch'ler Bulundu": "⏳  Unfinished batches found",
    "Tümünü Seç": "Select all", "Seçimi Kaldır": "Clear selection",
    "🗑  Seçilenleri Sil": "🗑  Delete selected", "▶  Seçilenleri Devam Ettir": "▶  Resume selected",
    "🗑  Sıfırla": "🗑  Reset", "📋  Kopyala": "📋  Copy", "✕  Kapat": "✕  Close",
    "PROJE GLOSSARYSİ": "PROJECT GLOSSARY", "KARAKTERLER": "CHARACTERS", "SERİ NOTLARI": "SERIES NOTES",
    "Henüz proje hafızası yok.\nAnaliz tamamlandıktan sonra otomatik dolar.": "No project memory yet.\nIt will populate automatically after analysis.",
    "Klasör Seç": "Select folder", "Altyazı Dosyaları Seç": "Select subtitle files",
    "İçinden Altyazı Alınacak Videoları Seç": "Select videos to extract subtitles from",
    "Glossary Seç": "Select glossary", "External Project Path Seç (subtitle_localizer)": "Select external project path (subtitle_localizer)",
    "Batch Output JSONL seç": "Select Batch output JSONL", "Orijinal SRT dosyasını seç (timestamps için)": "Select original SRT file (for timestamps)",
    "Çevrilmiş SRT olarak kaydet": "Save as translated SRT", "Post-işlenecek SRT dosyalarını seç": "Select SRT files to post-process",
    "API Anahtarı (boş = üstteki genel anahtar)": "API key (blank = general key above)",
    "Özel Model Sağlayıcı": "Custom model provider", "Özel Model Adı": "Custom model name",
    "Özel API URL": "Custom API URL", "Özel API Anahtarı (bu sağlayıcıya özel)": "Custom API key (for this provider)",
    "API PROFİLİ": "API PROFILE", "Sağlayıcı türü": "Provider type", "API anahtarı": "API key",
    "Modelleri getir": "Fetch models", "Kaydet": "Save", "API ANAHTARLARI": "API KEYS",
    "+ Yeni Profil": "+ New profile", "AKTİF YÖNLENDİRME": "ACTIVE ROUTING",
    "SHUAI ROTA TESTİ": "SHUAI ROUTE TEST", "ANAHTAR TESTİ": "KEY TEST",
    "ÇEVİRİ MOTORU": "TRANSLATION ENGINE", "Gelişmiş ayarlar": "Advanced settings",
    "Bağlam genişliğini, istek boyutunu ve hata toleransını ince ayarla.": "Fine-tune context width, request size, and error tolerance.",
    "Önerilen ayarlara dön": "Restore recommended settings", "Ayarları kaydet": "Save settings",
    "Hangi passları uygulayalım?": "Which passes should be applied?", "▶  Başlat": "▶  Start", "✕  İptal": "✕  Cancel",
    "Test ediliyor...": "Testing...", "Modele tek bir küçük deneme isteği gönderiliyor...": "Sending one small test request to the model...",
    "✓ Uygula": "✓ Apply", "Atla": "Skip", "✓ Sözlüğe Ekle": "✓ Add to glossary",
    "📂  Klasörde Göster": "📂  Show in folder", "Seçimleri Uygula": "Apply selections",
    "Tümünü Yeniden Çevir": "Retranslate all", "Bu Dillerle Devam Et": "Continue with these languages",
    "Ana Ekranda Düzenle": "Edit on main screen", "Bu Türlerle Devam Et": "Continue with these types",
    "Geçiş geçmişini aç / düzenle": "Open / edit pass history", "📂  Klasörü Aç": "📂  Open folder",
    "▶  Yeni Çeviri Başlat": "▶  Start new translation", "Altyazı Klasörü Ekle": "Add subtitle folder",
    "Hazır sağlayıcı": "Provider preset", "Süz: gemma, flash, mini…": "Filter: gemma, flash, mini…",
    "Altyazı akışı yok": "No subtitle stream", "✓ Model yanıt verdi. Devam Et düğmesi hazır.": "✓ The model responded. Continue is ready.",
    "KAYNAK": "SOURCE", "ÇEVİRİ": "TRANSLATION", "Çıkarılacak altyazı akışlarını seç": "Select subtitle streams to extract",
    "Seçilenleri Çıkar ve Ekle": "Extract and add selected", "En İyi Rotayı Kullan": "Use best route",
    "⟳  Rotaları Ölç": "⟳  Measure routes", "✓  Anahtarları Dene": "✓  Test keys",
    "CANLI İSTEK": "LIVE REQUEST", "TEST SATIRLARI": "TEST LINES", "SONUÇ": "RESULT",
    "1 satırı dene": "Test 1 line", "2 satırı dene": "Test 2 lines",
    "▶  Tam Çeviriyi Başlat": "▶  Start full translation", "Kapatmayı İptal Et": "Cancel shutdown",
    "Açıksa Çıkış klasörü YOK SAYILIR — her dosyanın\nçıktısı KENDİ geldiği klasöre, kendi adıyla\nyazılır. Farklı klasörlerden eklenen dosyalar\nkendi klasörüne geri döner. (Kaynak zaten .srt\nise çakışmayı önlemek için <isim>.tr.srt kullanılır.)": "When enabled, the Output folder is ignored. Each result is\nwritten beside its source with the same name. Files added\nfrom different folders return to their own folders. If the\nsource is already .srt, <name>.tr.srt prevents overwriting.",
    "LLM incelemesi: metni değiştiren geçişler kapanır,\nrapor ayrıntılı kalır — düzeltmeyi Codex/Claude yapar.\nDoğrudan teslim: program elinden geleni kendi düzeltir.": "LLM review disables text-rewriting passes while keeping a\ndetailed report for Codex/Claude. Direct delivery lets the\napplication apply its own safe corrections.",
    "Anında modda model kendi önceki\nçevirilerini görür: terim, ton ve sen/siz\ntutarlılığı artar. (Dosya içi sıralı işler)": "In synchronous mode, the model sees its earlier translations,\nimproving terminology, tone, and form-of-address consistency.\n(Sequential work within each file.)",
    "Kapalıyken çeviri sonunda eksik görünen cue'lar için\nek API isteği göndermez; cue kimliği, kaynak ve mevcut\nmetni loga yazar. Dosya tamamlanmış sayılmaz.": "When disabled, no extra API request is sent for missing cues.\nTheir IDs, source, and current text are logged, and the file is\nnot marked complete.",
    "Çeviriden önce dosyayı hızlıca okur:\nözet, karakterler, hitap (sen/siz) haritası\nve sabit terimler çıkarılıp prompt'a eklenir.\n(Yardımcı Analiz kapalıyken devreye girer)": "Reads the file before translation to extract a summary,\ncharacters, address/register map, and fixed terminology for\nthe prompt. Used when Assisted Analysis is disabled.",
    "Aynı dizinin bölümleri arasında terim,\nkarakter ve sen/siz kararlarını taşır.\nDosya adından S01E05 tespit edilir;\nilk bölümün kararları sabit kalır.": "Carries terminology, character, and address decisions between\nepisodes. Episode codes such as S01E05 are detected from the\nfilename, preserving earlier canon decisions.",
    "Seçilen sezonun bütün başarılı bölümleri bitince\ndizi hafızasındaki ad, terim ve hitap kanonunu\nkaynakla yeniden karşılaştırır; güvenli düzeltmeleri uygular.": "After all successful episodes in the selected season finish,\nrechecks names, terms, and address canon against the source\nand applies only validated corrections.",
    "Batch çevirisi bitince ana model dosyayı\nkaynakla karşılaştırıp baştan sona okur:\nterim/hitap tutarsızlıklarını ve çeviri\nhatalarını düzeltir. (~%40-60 ek maliyet)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "After Batch translation, the main model compares the entire\nfile with the source and repairs terminology, address, and\ntranslation errors. Adds roughly 40–60% cost.\n\nLeave OFF when another LLM will review the result.",
    "Dosya içinde bir özel ismin (Troy/Truva gibi)\nİNGİLİZCE biçimde kalmış (sızıntı) örneklerini,\nyalnızca doğru Türkçe biçim başka yerde açıkça\nvarsa otomatik düzeltir. Belirsiz durumlara\ndokunmaz. (gpt-5.4-mini ile)": "Repairs leaked source-language forms of proper names only when\nthe correct Turkish form is already established elsewhere in\nthe file. Ambiguous cases are untouched. (gpt-5.4-mini)",
    "  └ Düzeltmeleri uygula": "  └ Apply corrections",
    "Kapalıyken yalnızca rapor edilir. Uygulanan\ndüzeltmeler zaten iki katmanlı denetimden\ngeçer: plan sadece 'çevrilmeden kalmış' sınıfını\nseçer, aday da satır bazında doğrulanır.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "When disabled, findings are report-only. Applied corrections\npass two validation layers: the plan selects only untranslated\nleaks, then each candidate is checked line by line.\n\nLeave OFF when another LLM will review the result.",
    "Türkçe söz dizimi yüzünden 0,4 saniyelik bir\ncue'ya yığılan metni, önünde boş duran cue'ya\ngeri kaydırır. Zaman damgasına ve metnin\nkendisine dokunmaz. Sığmayan metin için\ndeğil (o condense işi) — yalnız yer varken.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Moves text crowded into a very short cue back into an empty\npreceding cue. Timestamps and wording stay unchanged. This is\nonly used when free cue space exists.\n\nLeave OFF when another LLM will review the result.",
    "Varsayılan güvenli mod. Şunları YALNIZ raporlar:\nteslim karantinası/taşıma, otomatik yeniden çeviri,\ntutarlılık süpürmesi, Kısaltma ve Cue-fill taşıma.\nBu geçişler aday bulur ve raporlar, ama\nçıktıyı DEĞİŞTİRMEZ. Sorunlu dosya yüklemeye\nhazır veya tamamlanmış sayılmaz.\nPolish, Native, QC ve Terim Normalizasyonu kendi\nanahtarlarıyla çalışmayı sürdürür — terim düzeltmesini\ndurdurmak için alttaki '└ Düzeltmeleri uygula'yı kapat.": "Safe default. Delivery quarantine/moves, automatic\nretranslation, consistency sweep, condensation, and cue-fill\nrelocation only report candidates without changing output. A\nproblem file is not marked ready or complete. Polish, Native,\nQC, and Terminology Normalization retain their own switches.",
    "YALNIZCA Batch+Hybrid modda. Dosyayı iki dalgaya\nböler; ilk dalga bitince çevirilerini ikinci dalgaya\nbağlam verir (batch'in eksik olduğu zincirleme).\nKaliteyi artırır ama BEKLEME SÜRESİNİ ~2×'ler\n(iki sıralı batch). Uzun/önemli dosyalar için.": "Batch + Assisted Analysis only. Splits the file into two waves\nand uses first-wave translations as context for the second.\nImproves continuity but roughly doubles waiting time. Intended\nfor long or important files.",
    "Seçili yardımcı model şüpheli anlam, bağlam ve\nterim noktalarını yalnız raporlar; altyazıyı değiştirmez.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "The selected helper reports suspicious meaning, context, and\nterminology without changing subtitles.\n\nLeave OFF when another LLM will review the result.",
    "Çeviri bittikten sonra seçili yardımcı modelle\nikinci geçiş — doğal Türkçeye çevirir.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Runs a second pass with the selected helper to improve natural\nTurkish after translation.\n\nLeave OFF when another LLM will review the result.",
    "Seçili yardımcı model çeviriyi inceler, şüpheli\nsatırları işaretler. Onayınla düzeltir.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "The selected helper reviews the translation, flags suspicious\nlines, and repairs them after approval.\n\nLeave OFF when another LLM will review the result.",
    "Türk izleyici gözüyle 'çevrilmiş gibi\nduran' satırları tespit edip doğallaştırır.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Finds lines that sound translated to a native Turkish viewer\nand makes them more natural.\n\nLeave OFF when another LLM will review the result.",
    "Türkçeyi tekrar İngilizceye çevirip anlamı\nkaynaktan SAPAN satırları yakalar; güvenli\nönerileri otomatik düzeltir ve raporlar.\n(Ek maliyet)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Back-translates Turkish to detect lines whose meaning diverges\nfrom the source, then applies and reports safe suggestions.\nAdds API cost. Leave OFF for external LLM review.",
    "Riskli ve çoklu-cue cümleleri kaynakla ±2 komşu\niçinde karşılaştırır; kapsam yaklaşık en az %65'tir.\nKüme güvenli değilse hiçbir değişiklik yapmaz.\n(Yüksek ek maliyet)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Compares risky multi-cue sentences with the source and ±2\nneighbors, targeting at least about 65% coverage. Unsafe groups\nremain unchanged. High additional cost.",
    "Kalite geçişleri (critic/polish/native/geri\nçeviri/QC) uygulanMADAN önceki ham çeviriyi\n<isim>.ham.srt olarak ayrıca kaydeder. Ana\nçıktıya dokunulmaz — bir geçiş bozarsa ham\nhali elinde kalır.": "Saves <name>.ham.srt before Critic, Polish, Native, back-\ntranslation, or QC passes. The main output is untouched, so the\nraw translation remains available if a pass regresses it.",
    "Çeviriden sözlüğe eklenecek terimleri\notomatik önerir. (gpt-5.4-mini ile)": "Automatically suggests terms to add to the glossary.\n(Uses gpt-5.4-mini.)",
    "42+ karakterlik satırları virgül/\nbağlaçtan böler. (EBU standardı)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Wraps lines longer than 42 characters at punctuation or\nconjunctions following EBU guidance. Leave OFF for external LLM review.",
    "'Peki, ananla ne yapacaksın' / 'ki?' gibi\nkelime kelime bölünmüş ardışık cue'ları\ntek bloğa toplar. Senkron korunur; sadece\ndevam eden (cümle bitmeyen) satırlar birleşir.\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Groups adjacent cues that split one sentence word by word.\nSynchronization is preserved; only unfinished continuations are\nmerged. Leave OFF for external LLM review.",
    "Üstteki birleştirmenin AI'lı sürümü: yardımcı\nmodel cue'ları ANLAMCA gruplar, satırları\nöğe sınırından kırar. Zamanlama/okuma hızı\ndeterministik korunur; kelimeler değişmez.\nAçıksa hızlı birleştirmenin yerine geçer\n(hata/anahtar yoksa ona düşer). (gpt-5.4-mini)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "AI version of cue merging: a helper groups cues semantically\nand breaks lines at constituent boundaries. Timing and reading\nspeed remain deterministic; words never change. Falls back to\nfast merging if unavailable. Leave OFF for external LLM review.",
    "Ekrana sığmayan (çok hızlı) satırları\nanlamı koruyarak kısaltır. (gpt-5.4-mini ile)\n\nLLM'e vereceksen KAPALI bırak — düzeltmeyi o yapacak.": "Condenses lines that read too quickly while preserving meaning.\nUses gpt-5.4-mini. Leave OFF for external LLM review.",
    "Çevirmeden önce filmi analiz eder:\nkarakter sesleri, ton, zorunlu terimler.\nBu bağlamla OpenAI çevirisi çok daha kaliteli.": "Analyzes character voices, tone, and required terminology before\ntranslation so the main model receives richer context.",
    "Yerleşik Reseller modellerinde kullanılır. Özel model veya API profili kendi URL'sini korur. Başarılı rota sabitlenir; 429 veren rota 5 dakika dinlendirilir.": "Used for built-in reseller models. Custom models and API profiles keep their own URL. Successful routes are pinned; a route returning 429 rests for five minutes.",
    "Final altyazıyı kaynakla; LLM'e vereceksen KAPALI bırak.\nCümle/fragment, komşu cue ve sahne bağlamında inceler.\nÖzne-nesne, kip/olumsuzluk, eksik-tekrar anlam ve Critic\nbozmasını cue numarasıyla raporlar; metni asla değiştirmez.\nEkonomik yaklaşık %35, Tam %100 kapsamdır.": "Reviews the final subtitle against the source using sentence,\nfragment, neighboring-cue, and scene context. Reports subject/object,\ntense/negation, omission/repetition, and Critic regressions by cue\nwithout changing text. Economy covers about 35%; Full covers 100%.\n\nLeave OFF when another LLM will review the result.",
}

# Common fragments cover dynamic status strings without touching model/domain data.
_FRAGMENT_EN = (
    ("dosya", "file"), ("Dosya", "File"), ("klasör", "folder"), ("Klasör", "Folder"),
    ("Seçilen", "Selected"), ("seçilen", "selected"), ("bulundu", "found"),
    ("Bekleniyor", "Waiting"), ("Bekliyor", "Waiting"), ("Tamamlandı", "Completed"),
    ("Başarısız", "Failed"), ("Durduruluyor", "Stopping"), ("Hazırlanıyor", "Preparing"),
)


def translate_ui_text(text: object, language: object = DEFAULT_UI_LANGUAGE) -> object:
    if not isinstance(text, str):
        return text
    if normalize_ui_language(language) == "Türkçe":
        # Window titles are generated from the stable English app name, unlike
        # widget copy whose source strings are Turkish.
        return text.replace("Subtitle Translator", "Altyazı Çevirisi")
    if text in EN:
        return EN[text]
    stripped = text.strip()
    if stripped in EN:
        return text[: len(text) - len(text.lstrip())] + EN[stripped] + text[len(text.rstrip()) :]
    # Only transform dynamic status text when a known UI fragment occurs.
    result = text
    for source, target in _FRAGMENT_EN:
        result = re.sub(rf"(?<!\w){re.escape(source)}(?!\w)", target, result)
    return result
