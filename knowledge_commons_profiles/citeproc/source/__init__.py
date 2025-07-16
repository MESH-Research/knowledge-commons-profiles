import contextlib
import logging

from knowledge_commons_profiles.citeproc import VARIABLES

logger = logging.getLogger(__name__)


# http://sourceforge.net/mailarchive/message.php?msg_id=25355232
# http://dret.net/bibconvert/tex2unicode
# ruff: noqa: I001


class CustomDict(dict):
    def __init__(self, args, required=None, optional=None, required_or=None):
        if required_or is None:
            required_or = []
        if optional is None:
            optional = set()
        if required is None:
            required = set()
        passed_keywords = set(args.keys())
        missing = required - passed_keywords
        if missing:
            raise TypeError(
                "The following required arguments are missing: "
                + ", ".join(missing)
            )
        required_or_merged = set()
        for required_options in required_or:
            if not passed_keywords & required_options:
                raise TypeError(
                    "Require at least one of: " + ", ".join(required_options)
                )
            required_or_merged |= required_options
        unsupported = (
            passed_keywords - required - optional - required_or_merged
        )
        if unsupported:
            cls_name = self.__class__.__name__
            msg = (f"The following arguments for {cls_name} "
                   f"are unsupported: " + ", ".join(unsupported))
            logger.debug(
                msg,
                stacklevel=2,
            )
        self.update(args)

    def __setattr__(self, name, value):
        self[name] = value

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise VariableError from KeyError


class Reference(CustomDict):
    def __init__(self, key, ref_type, **args):
        self.key = key
        self.type = ref_type
        # required_or = [set(csl.VARIABLES)]
        optional = {"uri", "container_uri", "contributor", "date"} | set(
            VARIABLES
        )
        super().__init__(args, optional=optional)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.key})"


class VariableError(Exception):
    pass


class Name(CustomDict):
    def __init__(self, **args):
        if "literal" in args:
            required, optional = {"literal"}, set()
        else:
            required = set()
            optional = {
                "family",
                "given",
                "dropping-particle",
                "non-dropping-particle",
                "suffix",
            }
        super().__init__(args, required, optional)

    def parts(self):
        if "literal" in self:
            return (None, self["literal"], None, None, None)
        return (
            self.get("given"),
            self.get("family"),
            self.get("dropping-particle"),
            self.get("non-dropping-particle"),
            self.get("suffix"),
        )


class DateBase(CustomDict):
    def __init__(self, args, required=None, optional=None):
        if optional is None:
            optional = set()
        if required is None:
            required = set()
        optional = {"circa"} | optional
        super().__init__(args, required, optional)
        # defaults
        if "circa" not in self:
            self["circa"] = False


class Date(DateBase):
    def __init__(self, **args):
        required = {"year"}
        optional = {"month", "day", "season"}
        if "day" in args and "month" not in args:
            msg = "When specifying the day, you should also specify the month"
            raise TypeError(msg)
        for key, value in args.items():
            with contextlib.suppress(ValueError):
                args[key] = int(value)

        super().__init__(args, required, optional)

    def sort_key(self):
        year = self.year
        month = self.get("month", 0)
        day = self.get("day", 0)
        return f"{year + 10000:05}{month:02}{day:02}"

    def is_nil(self):
        return (
            self.year == 0
            and self.get("month", 0) == 0
            and self.get("day", 0) == 0
        )


class LiteralDate(DateBase):
    def __init__(self, text, **args):
        self.text = text
        super().__init__(args)

    def sort_key(self):
        return self.text


class DateRange(DateBase):
    def __init__(self, **args):
        required = {"begin"}
        optional = {"end"}
        super().__init__(args, required, optional)

    def sort_key(self):
        begin = self.begin.sort_key()
        end = self.get("end", Date(year=0)).sort_key()
        return begin + "-" + end

    def __eq__(self, other):
        # TODO: for sorting
        raise NotImplementedError

    def __hash__(self):
        # TODO: for sorting
        raise NotImplementedError


class Citation(CustomDict):
    def __init__(self, cites, **kwargs):
        for cite in cites:
            cite.citation = self
        self.cites = cites
        super().__init__(kwargs)

    def __repr__(self):
        cites = ", ".join([cite.key for cite in self.cites])
        return f"{self.__class__.__name__}({cites})"


class CitationItem(CustomDict):
    def __init__(self, key, bibliography=None, **args):
        self.key = key.lower()
        optional = {"locator", "prefix", "suffix"}
        super().__init__(args, optional=optional)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.key})"

    @property
    def bibliography(self):
        return self.citation.bibliography

    @property
    def reference(self):
        return self.bibliography.source[self.key]

    @property
    def number(self):
        return self.bibliography.keys.index(self.key) + 1

    @property
    def has_locator(self):
        return "locator" in self

    def get_field(self, field):
        string = self.reference.get(field)
        if string is not None:
            return self.bibliography.formatter.preformat(string)

        return None

    def is_bad(self):
        return self.key not in self.bibliography.keys


class Locator:
    def __init__(self, label, identifier):
        self.label = label
        self.identifier = identifier


class BibliographySource(dict):
    def add(self, entry):
        self[entry.key] = entry


from knowledge_commons_profiles.citeproc.source.bibtex import (  # noqa: F401 E402
    bibtex,
)
from knowledge_commons_profiles.citeproc.source import json  # noqa: F401 E402
