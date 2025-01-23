"""
A management command to import data from the SQL file
"""

# pylint: disable=import-error,no-name-in-module,too-many-arguments
# pylint: disable=too-many-positional-arguments,no-member
from io import BytesIO

import rich
from django.core.management.base import BaseCommand
from django.db import transaction
from phpserialize import load as php_load
from rich.progress import track
from rich.progress import open as rich_open
from sqloxide import parse_sql

from newprofile.models import Profile, AcademicInterest


class Command(BaseCommand):
    """
    A management command to import data from the SQL file
    """

    help = "Import data from SQL into the Profile model"

    DATA_MATCHES = {
        "About": ("about_user", True),
        "Education": ("education", True),
        "Upcoming Talks and Conferences": ("upcoming_talks", False),
        "Publications": ("publications", False),
        "Projects": ("projects", False),
        "Site": ("site", False),
        "Institutional or Other Affiliation": (
            "institutional_or_other_affiliation",
            False,
        ),
        "Title": ("title", False),
        "Figshare URL": ("figshare_url", False),
        "Name": ("name", False),
        "<em>ORCID</em> iD": ("orcid", False),
        "Mastodon handle": ("mastodon", False),
    }

    @staticmethod
    def _build_final_dict(desired, field_index, final_dict, row):
        """
        Builds the final dictionary of fields for a given row.

        Args:
            desired (str): The field we want to grab from the row
            field_index (dict): A dictionary mapping field names to their
                positions in the row, as returned by sqloxide
            final_dict (dict): A dictionary that should be populated with the
                desired field's value
            row (dict): A row of data, as returned by sqloxide

        Returns:
            None
        """
        final_value = row[field_index[desired]]["Value"]
        if "SingleQuotedString" in final_value:
            final_value = final_value["SingleQuotedString"]

        elif "Number" in final_value:
            final_value = final_value["Number"][0]
        final_dict[desired] = final_value

    def _parse_multiple_tables(
        self,
        dump_filename,
        target_tables,
        desired_fields_list,
        field_indexes=None,
    ):
        """
        Parse the SQL dump for multiple tables and return rows of data for
        each table.

        Args:
            dump_filename (str): The path to the SQL dump file
            target_tables (list): List of tables to parse
            desired_fields_list (list): List of lists, where each inner list
                contains the desired fields for the corresponding table in
                target_tables
            field_indexes (list or None, optional): List of pre-computed field
            indexes for each table. If not provided, will be computed.
            Defaults to None.

        Returns:
            list: A list of lists, where each inner list contains dictionaries
            representing rows for each target table
        """
        if field_indexes is None:
            field_indexes = [{} for _ in target_tables]

        # Initialize results list for each table
        all_tables_rows = [[] for _ in target_tables]

        with rich_open(dump_filename, "r", errors="ignore") as f:
            statement_counters = [0 for _ in target_tables]

            for line in f:
                try:
                    parser = parse_sql(line, dialect="mysql")
                except ValueError:
                    continue

                if len(parser) > 0:
                    for statement in parser:
                        self._parse_data(
                            all_tables_rows,
                            desired_fields_list,
                            field_indexes,
                            statement,
                            statement_counters,
                            target_tables,
                        )

        return all_tables_rows

    def _parse_data(
        self,
        all_tables_rows,
        desired_fields_list,
        field_indexes,
        statement,
        statement_counters,
        target_tables,
    ):
        if isinstance(statement, dict):
            for key, val in statement.items():
                self._handle_insert(
                    all_tables_rows,
                    desired_fields_list,
                    field_indexes,
                    key,
                    statement_counters,
                    target_tables,
                    val,
                )

    def _handle_insert(
        self,
        all_tables_rows,
        desired_fields_list,
        field_indexes,
        key,
        statement_counters,
        target_tables,
        val,
    ):
        if key == "Insert":
            # Check if current table is one we're
            # looking for
            table_name = val["table_name"][0]["value"]

            if table_name in target_tables:
                table_idx = self._build_index(
                    desired_fields_list,
                    field_indexes,
                    statement_counters,
                    table_name,
                    target_tables,
                    val,
                )

                # Process rows for this table
                for row in val["source"]["body"]["Values"]["rows"]:
                    final_dict = {}

                    for desired in desired_fields_list[table_idx]:
                        self._build_final_dict(
                            desired,
                            field_indexes[table_idx],
                            final_dict,
                            row,
                        )

                    all_tables_rows[table_idx].append(final_dict)

    @staticmethod
    def _build_index(
        desired_fields_list,
        field_indexes,
        statement_counters,
        table_name,
        target_tables,
        val,
    ):
        table_idx = target_tables.index(table_name)
        statement_counters[table_idx] += 1
        # Create field index for this table if
        # not exists
        if len(field_indexes[table_idx]) == 0:
            for item in val["columns"]:
                if item["value"] in desired_fields_list[table_idx]:
                    field_indexes[table_idx][item["value"]] = val[
                        "columns"
                    ].index(item)
        return table_idx

    @transaction.atomic
    def _deserialize_academic_interests(self) -> None:
        """
        Deserialize a list of academic interests from a list of Profile objects
        into a list of objects.

        This method takes a list of Profile objects and deserializes the
        academic_interests field into a list of AcademicInterest objects.
        """
        profiles = Profile.objects.all()

        for profile in profiles:
            academic_interests = profile.academic_interests.all()

            if len(academic_interests) == 0:
                continue

            interest = academic_interests[0]

            # The text field is a serialized PHP array, so we need to
            # deserialize it first.
            stream = BytesIO(str.encode(interest.text))
            new_array = php_load(stream)

            profile.academic_interests.clear()

            for item in new_array:
                # If the academic interest does not exist, create a new
                # instance of it. If it does exist, just add it to the
                # many-to-many field.
                profile.academic_interests.add(
                    AcademicInterest.objects.get_or_create(text=item)[0]
                )

            profile.save()

    @staticmethod
    def _unescape(input_string: str) -> str:
        """
        Escapes a string with special characters by converting it to a
        latin-1 encoded string and then decoding it as a unicode-escape
        string.

        This is a workaround for a bug in the MySQL dump file where
        special characters are escaped with a backslash, but the backslash
        is not escaped itself.

        For example, the string "hello\\world" is escaped to
        "hello\\\\world" in the MySQL dump file.

        This function takes an input string and escapes it by converting
        it to a latin-1 encoded string and then decoding it as a
        unicode-escape string.

        Args:
            input_string: The string to be escaped.

        Returns:
            The escaped string.
        """
        return input_string.encode("latin-1", "backslashreplace").decode(
            "unicode-escape"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """
        This command imports a MySQL dump file into the Django database.
        """
        rich.print("Parsing users, data_fields, and data_values...")

        users, data_fields, data_values = self._parse_multiple_tables(
            dump_filename="/home/martin/hcprod.sql",
            target_tables=[
                "wp_users",
                "wp_bp_xprofile_fields",
                "wp_bp_xprofile_data",
            ],
            desired_fields_list=[
                ["id", "user_login", "user_email", "user_registered"],
                ["id", "type", "name", "field_order"],
                ["id", "field_id", "user_id", "value"],
            ],
            field_indexes=[
                {
                    "id": 0,
                    "user_login": 1,
                    "user_email": 4,
                    "user_registered": 6,
                },
                {"id": 0, "type": 3, "name": 4, "field_order": 8},
                {"id": 0, "field_id": 1, "user_id": 2, "value": 3},
            ],
        )

        already_printed = []

        for user in track(users):
            # get the model
            profile, _ = Profile.objects.get_or_create(
                username=user["user_login"]
            )
            profile.central_user_id = user["id"]
            profile.email = user["user_email"]

            # delete profile's academic interests
            try:
                profile.academic_interests.clear()
            except AttributeError:
                pass

            # now get the data values for this user and add them to the model
            for data_value in data_values:
                self._handle_values(
                    already_printed, data_fields, data_value, profile, user
                )

            profile.save()

        self._deserialize_academic_interests()

    def _handle_values(
        self, already_printed, data_fields, data_value, profile, user
    ):

        if data_value["user_id"] == user["id"]:
            for data_field in data_fields:
                if data_field["id"] == data_value["field_id"]:
                    # unescape the value
                    if data_field["name"] == "Academic Interests":
                        interest, _ = AcademicInterest.objects.get_or_create(
                            text=data_value["value"]
                        )
                        profile.academic_interests.add(interest)
                    elif data_field["name"] in self.DATA_MATCHES:
                        setattr(
                            profile,
                            self.DATA_MATCHES[data_field["name"]][0],
                            (
                                self._unescape(data_value["value"])
                                if self.DATA_MATCHES[data_field["name"]][1]
                                else data_value["value"]
                            ),
                        )
                    elif data_field["name"] not in already_printed:
                        rich.print(
                            f'Unhandled field: "' f"{data_field['name']}\""
                        )
                        already_printed.append(data_field["name"])
