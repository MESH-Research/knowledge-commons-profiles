from pathlib import Path
from warnings import warn

from lxml import etree

from knowledge_commons_profiles.citeproc import LOCALES_PATH
from knowledge_commons_profiles.citeproc import SCHEMA_PATH
from knowledge_commons_profiles.citeproc import STYLES_PATH
from knowledge_commons_profiles.citeproc.formatter import html
from knowledge_commons_profiles.citeproc.model import CitationStylesElement


class CitationStylesXML:
    def __init__(self, f, validate=True):
        lookup = etree.ElementNamespaceClassLookup()
        namespace = lookup.get_namespace("http://purl.org/net/xbiblio/csl")
        namespace[None] = CitationStylesElement
        namespace.update(
            {
                cls.__name__.replace("_", "-").lower(): cls
                for cls in CitationStylesElement.__subclasses__()
            }
        )

        self.parser = etree.XMLParser(
            remove_comments=True, encoding="UTF-8", no_network=True
        )
        self.parser.set_element_class_lookup(lookup)
        self.xml = etree.parse(f, self.parser)  # noqa: S320
        if validate:
            self.schema = etree.RelaxNG(etree.parse(SCHEMA_PATH))  # noqa: S320
            if not self.schema.validate(self.xml):
                err = self.schema.error_log
                msg = f"XML file didn't pass schema validation:\n{err}"
                warn(msg, stacklevel=2)
                # TODO: proper error reporting
        self.root = self.xml.getroot()


class CitationStylesLocale(CitationStylesXML):
    def __init__(self, locale, validate=True):
        locale_path = Path(LOCALES_PATH) / f"locales-{locale}.xml"
        try:
            super().__init__(locale_path, validate=validate)
        except OSError:
            msg = f"'{locale}' is not a known locale"
            raise ValueError(msg) from OSError


class CitationStylesStyle(CitationStylesXML):
    def __init__(self, style, locale=None, validate=True):
        try:
            if not Path(style).exists():
                style = Path(STYLES_PATH) / f"{style}.csl"
        except TypeError:
            pass
        try:
            super().__init__(style, validate=validate)
        except OSError:
            msg = f"'{style}' is not a known style"
            raise ValueError(msg) from OSError
        if locale is None:
            locale = self.root.get("default-locale", "en-US")
        self.root.set_locale_list(locale, validate=validate)

    def has_bibliography(self):
        return self.root.bibliography is not None

    def render_citation(self, citation, cites, callback=None):
        return self.root.citation.render(citation, cites, callback)

    def sort_bibliography(self, citation_items):
        return self.root.bibliography.sort(citation_items)

    def render_bibliography(self, citation_items):
        return self.root.bibliography.render(citation_items)


class CitationStylesBibliography:
    def __init__(self, style, source, formatter=html):
        self.style = style
        self.source = source
        self.formatter = self.style.root.formatter = formatter
        self.keys = []
        self.items = []
        self._cites = []

    def register(self, citation, callback=None):
        citation.bibliography = self
        for item in citation.cites:
            if item.key in self.source:
                if item.key not in self.keys:
                    self.keys.append(item.key)
                    self.items.append(item)
            elif callback is not None:
                callback(item)

    def sort(self):
        self.items = self.style.sort_bibliography(self.items)
        self.keys = [item.key for item in self.items]

    def cite(self, citation, callback):
        return self.style.render_citation(citation, self._cites, callback)

    def bibliography(self):
        return self.style.render_bibliography(self.items)
