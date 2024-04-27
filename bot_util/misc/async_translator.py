import gettext
import os


class AsyncTranslator:
    def __init__(self, language_code):
        if language_code is None:
            language_code = "en"
        self.language_code = language_code

    async def __aenter__(self):
        lang = gettext.translation(
            "mifbot2",
            localedir=os.path.abspath("./locales"),
            languages=[self.language_code],
            fallback=True,
        )
        return lang

    async def __aexit__(self, exc_type, exc, tb):
        del self
