# -*- coding: utf-8 -*-
"""Hazır sağlayıcı ön ayarları.

Program zaten herhangi bir OpenAI uyumlu adrese bağlanabiliyordu; eksik olan
kullanıcının o adresi EZBERE bilmek zorunda olmasıydı. Buradaki kayıt, "Google
Gemini" seçince adresin kendiliğinden dolmasını sağlar.

ADRESLER ÖLÇÜLDÜ, ezberden yazılmadı (2026-08-29). Her adrese anahtarsız bir
`/models` isteği atıldı; uç nokta varsa yetki hatası döner, yoksa DNS/404:

    Google AI Studio   400  "Please pass a valid API key"      -> adres doğru
    OpenRouter         200  model listesi anahtarsız açık      -> adres doğru
    Groq               401  "Invalid API Key"                  -> adres doğru
    DeepSeek           401  "Authentication Fails"             -> adres doğru
    Together AI        401  "Unauthorized"                     -> adres doğru
    Mistral            401                                     -> adres doğru
    xAI                400  "Incorrect API key provided"       -> adres doğru
    Cerebras           401                                     -> adres doğru
    Fireworks          401  "The API key you provided..."      -> adres doğru
    Nebius             401                                     -> adres doğru
    OpenAI             401  (kontrol)                          -> adres doğru

400 dönen ikisi de gövdesinde anahtar istiyor; yani uç nokta yanıt veriyor.

MODEL ADLARI SABİT TUTULMAZ. Sağlayıcılar model çıkarır ve kaldırır; koda
gömülen liste birkaç ay sonra yalan söyler. `ornek_modeller` yalnız bir
başlangıç ipucudur — doğrusu profil penceresindeki "Modelleri getir"
düğmesiyle sağlayıcının KENDİ listesinden seçmektir.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Saglayici:
    """Bir sağlayıcının bağlanma bilgisi."""

    etiket: str
    base_url: str
    tur: str = "openai_compatible"
    anahtar_adresi: str = ""
    not_: str = ""
    ornek_modeller: tuple = ()
    yerel: bool = False


# Sıra kullanıcıya göredir: önce resmi, sonra en çok istenenler.
SAGLAYICILAR: dict[str, Saglayici] = {

    "OpenAI Resmi": Saglayici(
        etiket="OpenAI Resmi",
        base_url="https://api.openai.com/v1",
        tur="openai_official",
        anahtar_adresi="https://platform.openai.com/api-keys",
        not_="Toplu (Batch) mod YALNIZ burada çalışır; gerçek Batch API'sini "
             "başka sağlayıcı sunmuyor.",
        ornek_modeller=("gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"),
    ),

    "Google AI Studio (Gemini · Gemma)": Saglayici(
        etiket="Google AI Studio (Gemini · Gemma)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        anahtar_adresi="https://aistudio.google.com/apikey",
        not_="Gemini Flash modelleri hızlı ve ucuzdur; Gemma açık modelleri de "
             "buradan çağrılır. Model adı ön ek almaz (`gemini-3.5-flash`).",
        ornek_modeller=("gemini-3.5-flash", "gemini-3.5-flash-lite",
                        "gemini-2.5-flash", "gemma-4-31b-it"),
    ),

    "OpenRouter": Saglayici(
        etiket="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        anahtar_adresi="https://openrouter.ai/keys",
        not_="Tek anahtarla yüzlerce modele erişir (Gemini, Gemma, Llama, "
             "Qwen, DeepSeek, Claude…). Model adı sağlayıcı ön eki alır: "
             "`google/gemma-4-31b-it`. `:free` ile biten ücretsiz sürümler "
             "vardır ama hız sınırı serttir.",
        ornek_modeller=("google/gemini-3.5-flash", "google/gemma-4-31b-it",
                        "google/gemma-4-31b-it:free",
                        "deepseek/deepseek-v4-flash"),
    ),

    "Groq": Saglayici(
        etiket="Groq",
        base_url="https://api.groq.com/openai/v1",
        anahtar_adresi="https://console.groq.com/keys",
        not_="Çok hızlı çıkarım. Açık modeller (Gemma, Llama, Qwen) sunar; "
             "kapalı modeller yoktur.",
        ornek_modeller=("gemma2-9b-it", "llama-3.3-70b-versatile"),
    ),

    "DeepSeek": Saglayici(
        etiket="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        anahtar_adresi="https://platform.deepseek.com/api_keys",
        not_="Ucuz ve uzun bağlamlı. Türkçe çıktısını bir dosyada ölçmeden "
             "ana çeviriye almayın.",
        ornek_modeller=("deepseek-chat", "deepseek-reasoner"),
    ),

    "Mistral": Saglayici(
        etiket="Mistral",
        base_url="https://api.mistral.ai/v1",
        anahtar_adresi="https://console.mistral.ai/api-keys",
        ornek_modeller=("mistral-large-latest", "mistral-small-latest"),
    ),

    "xAI (Grok)": Saglayici(
        etiket="xAI (Grok)",
        base_url="https://api.x.ai/v1",
        anahtar_adresi="https://console.x.ai",
        ornek_modeller=("grok-4", "grok-4-fast"),
    ),

    "Together AI": Saglayici(
        etiket="Together AI",
        base_url="https://api.together.xyz/v1",
        anahtar_adresi="https://api.together.ai/settings/api-keys",
        not_="Açık ağırlıklı modelleri barındırır; Gemma ve Llama ailesi "
             "buradan da çağrılabilir.",
        ornek_modeller=("google/gemma-2-27b-it",),
    ),

    "Cerebras": Saglayici(
        etiket="Cerebras",
        base_url="https://api.cerebras.ai/v1",
        anahtar_adresi="https://cloud.cerebras.ai",
        not_="Açık modellerde çok yüksek hız.",
        ornek_modeller=("llama-3.3-70b",),
    ),

    "Fireworks": Saglayici(
        etiket="Fireworks",
        base_url="https://api.fireworks.ai/inference/v1",
        anahtar_adresi="https://fireworks.ai/account/api-keys",
        ornek_modeller=("accounts/fireworks/models/llama-v3p3-70b-instruct",),
    ),

    "Nebius": Saglayici(
        etiket="Nebius",
        base_url="https://api.studio.nebius.com/v1",
        anahtar_adresi="https://studio.nebius.com",
        ornek_modeller=("google/gemma-2-27b-it",),
    ),

    "Anthropic / Claude": Saglayici(
        etiket="Anthropic / Claude",
        base_url="https://api.anthropic.com/v1",
        tur="anthropic",
        anahtar_adresi="https://console.anthropic.com/settings/keys",
        ornek_modeller=("claude-sonnet-5", "claude-opus-5"),
    ),

    "Ollama (bu bilgisayarda)": Saglayici(
        etiket="Ollama (bu bilgisayarda)",
        base_url="http://localhost:11434/v1",
        anahtar_adresi="",
        yerel=True,
        not_="Model kendi bilgisayarınızda çalışır: ücretsiz, internet "
             "gerekmez, veri dışarı çıkmaz — ama hız donanımınıza bağlıdır. "
             "Önce Ollama'yı kurup `ollama pull gemma3` ile modeli indirin. "
             "API anahtarı alanına herhangi bir şey yazabilirsiniz.",
        ornek_modeller=("gemma3", "gemma3:27b", "llama3.3"),
    ),

    "LM Studio (bu bilgisayarda)": Saglayici(
        etiket="LM Studio (bu bilgisayarda)",
        base_url="http://localhost:1234/v1",
        anahtar_adresi="",
        yerel=True,
        not_="LM Studio'da 'Local Server'ı başlatın. Anahtar alanı boş "
             "bırakılabilir.",
        ornek_modeller=(),
    ),
}


SAGLAYICI_ADLARI = tuple(SAGLAYICILAR)
OZEL = "Özel adres (elle gir)"


def url_ile_bul(base_url: str):
    """Adresten sağlayıcıyı bulur; kayıtlı değilse None.

    Karşılaştırma konak adı üzerinden yapılır: kullanıcı adresin sonuna
    eğik çizgi koyabilir ya da `/v1`'i düşürebilir.
    """
    from urllib.parse import urlparse

    hedef = (urlparse(str(base_url or "")).hostname or "").casefold()
    if not hedef:
        return None
    for saglayici in SAGLAYICILAR.values():
        konak = (urlparse(saglayici.base_url).hostname or "").casefold()
        if konak and konak == hedef:
            return saglayici
    return None


def yerel_mi(base_url: str) -> bool:
    """Adres bu bilgisayarı mı gösteriyor (anahtar gerekmez)."""
    from urllib.parse import urlparse

    konak = (urlparse(str(base_url or "")).hostname or "").casefold()
    return konak in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
