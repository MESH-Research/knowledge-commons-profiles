def escape(text):
    text = text.replace("*", r"\*")
    return text.replace("`", r"\`")


def preformat(text):
    return escape(str(text))


class RoleWrapper(str):
    __slots__ = ()

    role = None

    @classmethod
    def _wrap(cls, text):
        return f":{cls.role}:`{text}`"

    def __new__(cls, text):
        return super().__new__(cls, cls._wrap(text))


class Italic(RoleWrapper):
    role = "emphasis"


class Oblique(Italic):
    pass


class Bold(RoleWrapper):
    role = "strong"


Light = str
Underline = str


class Superscript(RoleWrapper):
    role = "superscript"


class Subscript(RoleWrapper):
    role = "subscript"


SmallCaps = str
