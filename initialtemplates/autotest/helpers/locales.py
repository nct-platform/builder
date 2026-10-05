"""The project's languages, and every user-visible string the tests assert on — per locale.

A test never hard-codes one language. The interface language is a USER preference stored on the server, so the
same test runs on an English page today and on a Russian one after somebody switched their profile; and the
scenarios must hold in EVERY locale the project declares. So every caption, message and label a test looks for
comes from here, keyed by locale.

`mrjun.py autotest scaffold` writes LOCALES and DEFAULT_LOCALE from the export (tenant.json). Everything else is
written by the builder from the export it authored — the captions are the ones the builder itself put into the
project, so they are known before the project ever runs.
"""

# Every locale the project declares — the default first. (Replaced by `mrjun.py autotest scaffold`.)
LOCALES = ("en_US",)
DEFAULT_LOCALE = "en_US"

# The language picker is driven by each item's FLAG (the locale's country), so no caption is needed for any
# language. Only when two of the project's locales share a country (say en_US and es_US) does the picker need the
# item's caption — the language's own name, as the picker renders it — to tell them apart:
LOCALE_MENU_LABEL: dict = {
    # "es_US": "español",
}

# Left-nav section headings per locale, in nav order — the navigation and i18n tests assert them.
NAV_SECTIONS: dict = {
    # "en_US": ["<SECTION 1>", "<SECTION 2>"],
}

# Every caption a test reads or clicks, per locale: register columns, form labels, action names, refusal texts.
# Key it by something stable (the control's field expression, the action id) — never by one language's text.
CAPTIONS: dict = {
    # "order.number": {"en_US": "Order number", "ru_RU": "Номер заказа", "hy_AM": "Պատվերի համար"},
}

# Codes and prefixes that must read the SAME in every locale (document numbers, item codes, status codes that are
# shown as codes on purpose). The leak checks exempt them; a translated code is a defect.
NEVER_TRANSLATED: list = [
    # "ORD-",
]


def caption(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """The caption `key` in `locale`; fails loudly when the builder did not record it."""
    try:
        per_locale = CAPTIONS[key]
    except KeyError:
        raise KeyError(f"helpers/locales.py has no caption {key!r} — add it for every locale in LOCALES") from None
    if locale not in per_locale:
        raise KeyError(f"caption {key!r} has no {locale} text — the scenarios run in every locale in LOCALES")
    return per_locale[locale]


def captions(key: str) -> list:
    """The caption `key` in every locale — for a label check that must hold whatever the session language is."""
    return [caption(key, loc) for loc in LOCALES]
