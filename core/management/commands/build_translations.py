"""
Build locale/<lang>/LC_MESSAGES/django.po and .mo without GNU gettext.

Django's makemessages/compilemessages need the gettext binaries, which are
rarely installed on Windows. This command extracts the strings marked in the
templates ({% translate %}, {% blocktranslate %}, _("...")), merges them with
the translations stored in locale/<lang>/translations.json and compiles the
.mo file with polib.

    python manage.py build_translations            # build en
    python manage.py build_translations --check    # fail if a string is untranslated
"""

import json
import re
from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

TRANSLATE_RE = re.compile(r"""\{%\s*translate\s+(?P<q>["'])(?P<msg>.*?)(?P=q)(?:\s+as\s+\w+)?\s*%\}""")
UNDERSCORE_RE = re.compile(r"""_\((?P<q>["'])(?P<msg>.*?)(?P=q)\)""")
BLOCK_RE = re.compile(
    r"\{%\s*blocktranslate(?P<args>[^%]*)%\}(?P<body>.*?)\{%\s*endblocktranslate\s*%\}",
    re.DOTALL,
)
PLURAL_RE = re.compile(r"\{%\s*plural\s*%\}")
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _block_msgid(text: str) -> str:
    # Same transformation as Django's {% blocktranslate %}: literal % doubled, {{ var }} -> %(var)s.
    return VAR_RE.sub(lambda m: f"%({m.group(1)})s", text.replace("%", "%%"))


def extract(template_dir: Path) -> dict[str, str | None]:
    """{msgid: msgid_plural or None}"""
    messages: dict[str, str | None] = {}
    for path in sorted(template_dir.rglob("*.html")) + sorted(template_dir.rglob("*.txt")):
        content = path.read_text(encoding="utf-8")
        for regex in (TRANSLATE_RE, UNDERSCORE_RE):
            for match in regex.finditer(content):
                messages.setdefault(match.group("msg"), None)
        for match in BLOCK_RE.finditer(content):
            parts = PLURAL_RE.split(match.group("body"))
            singular = _block_msgid(parts[0])
            plural = _block_msgid(parts[1]) if len(parts) > 1 else None
            messages[singular] = plural
    return messages


class Command(BaseCommand):
    help = "Extrait les chaînes des templates et compile les traductions (sans gettext)."

    def add_arguments(self, parser):
        parser.add_argument("--language", default="en")
        parser.add_argument("--check", action="store_true", help="Échoue si une chaîne n'est pas traduite.")

    def handle(self, *args, **options):
        language = options["language"]
        locale_dir = Path(settings.LOCALE_PATHS[0]) / language / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        translations_file = Path(settings.LOCALE_PATHS[0]) / language / "translations.json"
        translations = json.loads(translations_file.read_text(encoding="utf-8")) if translations_file.exists() else {}

        messages = extract(Path(settings.BASE_DIR) / "templates")
        po = polib.POFile()
        po.metadata = {
            "Project-Id-Version": "DevHire",
            "Language": language,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
            "Plural-Forms": "nplurals=2; plural=(n != 1);",
        }
        missing = []
        for msgid, plural in sorted(messages.items()):
            value = translations.get(msgid)
            if plural is not None:
                forms = value if isinstance(value, list) else ["", ""]
                if not all(forms):
                    missing.append(msgid)
                po.append(polib.POEntry(msgid=msgid, msgid_plural=plural, msgstr_plural={0: forms[0], 1: forms[1]}))
            else:
                if not value:
                    missing.append(msgid)
                po.append(polib.POEntry(msgid=msgid, msgstr=value or ""))

        po.save(str(locale_dir / "django.po"))
        po.save_as_mofile(str(locale_dir / "django.mo"))

        unused = sorted(set(translations) - set(messages))
        self.stdout.write(f"{len(messages)} chaînes, {len(missing)} non traduites, {len(unused)} inutilisées.")
        for msgid in missing:
            self.stdout.write(f"  À traduire : {msgid!r}")
        if options["check"] and missing:
            raise CommandError("Des chaînes ne sont pas traduites.")
