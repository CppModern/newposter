import translation.en as en
import translation.heb as heb


class Localisation:
    def __init__(self, lang="en"):
        self.code = lang

    def __getattr__(self, item):
        if self.code == "en":
            return getattr(en, item)
        return getattr(heb, item)

    def get(self, attr) -> str:
        return getattr(self, attr)
