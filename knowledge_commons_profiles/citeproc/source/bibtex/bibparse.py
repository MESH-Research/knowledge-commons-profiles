# http://maverick.inria.fr/~Xavier.Decoret/resources/xdkbibtex/bibtex_summary.html
# http://www.lsv.ens-cachan.fr/~markey/bibla.php?lang=en
from pathlib import Path


class BibTeXEntry(dict):
    def __init__(self, document_type, attributes):
        super().__init__(attributes)
        self.document_type = document_type


class BibTeXDecodeError(Exception):
    """Exception raised when the encoding passed to BibTeXParser cannot decode
    the BibTeX database file."""

    def __init__(self, decode_error, line_number):
        msg = (
            f"'{decode_error.encoding}' decode error on line {line_number}: "
            f"{decode_error.reason}. Please specify the BibTeX's "
            "database character encoding when instantiating BibTeXParser."
        )
        super().__init__(msg)
        self.line_number = line_number
        self.decode_error = decode_error


class BibTeXParser(dict):
    standard_variables = {
        "jan": "January",
        "feb": "February",
        "mar": "March",
        "apr": "April",
        "may": "May",
        "jun": "June",
        "jul": "July",
        "aug": "August",
        "sep": "September",
        "oct": "October",
        "nov": "November",
        "dec": "December",
    }

    def __init__(self, file_or_filename, encoding="ascii"):
        """
        Initialize a new BibTeXParser object.
        """
        try:
            with Path.open(file_or_filename, encoding=encoding) as self.file:
                self.variables = {}
                self.preamble = ""
                self._parse(self.file)

        except TypeError:
            self.file = file_or_filename

    def _parse(self, file):
        while True:
            try:
                entry = self._parse_entry(file)
                if entry is not None:
                    entry_type, key, attributes = entry
                    self[key] = BibTeXEntry(entry_type, attributes)
            except UnicodeDecodeError as decode_error:
                # I'm not convinced the following is robust
                safe_part = decode_error.object[: decode_error.start]
                line_number = len(safe_part.splitlines())
                offset = file.tell() - len(decode_error.object)
                if offset > 0:
                    file.seek(0)
                    line_number += file.read(offset).count(file.newlines)
                raise BibTeXDecodeError(
                    decode_error, line_number
                ) from decode_error
            except EOFError:
                break

    def _parse_entry(self, file):
        self.check_char(file)

        entry_type = ""

        while True:
            char = file.read(1)
            if char in "{(":
                sentinel = "}" if char == "{" else ")"
                break
            entry_type += char
            if entry_type.lower().startswith("comment"):
                self._jump_to_next_line(file)
                return None

        entry_type = entry_type.strip().lower()

        if entry_type == "string":
            name = self._parse_name(file)
            value = self._parse_value(file)
            self.variables[name] = value
            assert self._eat_whitespace(file) == sentinel
            return None
        if entry_type == "preamble":
            self.preamble += self._parse_value(file)
            assert self._eat_whitespace(file) == sentinel
            return None
        key = self._parse_key(file)
        entry = {}

        self.parse_values(entry, file, sentinel)

        return entry_type.strip().lower(), key, entry

    def parse_values(self, entry, file, sentinel):
        """
        Parse values from stream
        """
        while True:
            name = self._parse_name(file)
            value = self._parse_value(file)
            entry[name] = value
            char = self._eat_whitespace(file)
            if char != ",":
                if char != sentinel:
                    assert char in " \t\n\r"
                    assert self._eat_whitespace(file) == sentinel
                break
            restore_point = file.tell()
            if self._eat_whitespace(file) == sentinel:
                break
            file.seek(restore_point)

    def check_char(self, file):
        """
        Check that the first character is @
        """
        while True:
            char = file.read(1)
            if char == "@":
                break
            if char == "":
                raise EOFError

    def _parse_key(self, file):
        """
        Parse key
        """
        key = ""
        char = file.read(1)
        while char != ",":
            key += char
            char = file.read(1)
            if not char:
                error = "End of file while parsing key"
                raise ValueError(error)
        return key.strip().lower()

    def _parse_name(self, file):
        name = ""
        char = self._eat_whitespace(file)
        while True:
            if char == "=":
                break
            name += char
            char = file.read(1)
        return name.strip().lower()

    def _parse_value(self, file):
        char = self._eat_whitespace(file)
        if char in '{"':
            value = self._parse_string(file, char)
        elif char.isalpha():
            value = self._parse_variable(file, char)
        else:
            value = self._parse_integer(file, char)

        restore_position = file.tell()
        char = self._eat_whitespace(file)
        if char == "#":
            value += self._parse_value(file)
        else:
            file.seek(restore_position)
        return value

    def _parse_string(self, file, opening_character):
        closing_character = '"' if opening_character == '"' else "}"
        string = ""
        depth = 0
        while True:
            char = file.read(1)
            if not char:
                error = "End of file while parsing string value"
                raise ValueError(error)
            if char == "{":
                depth += 1
            elif depth == 0 and char == closing_character:
                break
            elif char == "}":
                depth -= 1
            string += char
        return string

    def _parse_variable(self, file, char):
        key = ""
        restore_point = file.tell()
        while char.isalnum() or char in "-_":
            key += char
            restore_point = file.tell()
            char = file.read(1)
        file.seek(restore_point)
        if key.lower() in self.variables:
            value = self.variables[key.lower()]
        else:
            value = self.standard_variables[key.lower()]
        return value

    def _parse_integer(self, file, char):
        integer = ""
        restore_point = file.tell()
        while char.isdigit():
            integer += char
            restore_point = file.tell()
            char = file.read(1)
        file.seek(restore_point)
        return int(integer)

    # TODO: rename to next_token?
    def _eat_whitespace(self, file):
        char = file.read(1)
        while char in " \t\n\r":
            char = file.read(1)
        return char

    def _jump_to_next_line(self, file):
        char = ""
        while char != "\n":
            restore_point = file.tell()
            char = file.read(1)
        file.seek(restore_point)

    def _split_name(self, name):
        pass
