"""
A management command to import data from the SQL file
"""

from io import BytesIO

import rich
from django.core.management.base import BaseCommand
from django.db import transaction
from phpserialize import load as phpload
from rich.progress import track, open
from sqloxide import parse_sql

from newprofile.models import Profile, AcademicInterest


class Command(BaseCommand):
    help = "Import data from SQL into the Profile model"

    def _build_final_dict(self, desired, field_index, final_dict, row):
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

        with open(dump_filename, "r", errors="ignore") as f:
            statement_counters = [0 for _ in target_tables]

            for line in f:
                try:
                    parser = parse_sql(line, dialect="mysql")
                except ValueError:
                    continue

                if len(parser) > 0:
                    for statement in parser:
                        if type(statement) is dict:
                            for key, val in statement.items():
                                if key == "Insert":
                                    # Check if current table is one we're looking for
                                    table_name = val["table_name"][0]["value"]
                                    if table_name in target_tables:
                                        table_idx = target_tables.index(
                                            table_name
                                        )
                                        statement_counters[table_idx] += 1

                                        # Create field index for this table if not exists
                                        if len(field_indexes[table_idx]) == 0:
                                            for item in val["columns"]:
                                                if (
                                                    item["value"]
                                                    in desired_fields_list[
                                                        table_idx
                                                    ]
                                                ):
                                                    field_indexes[table_idx][
                                                        item["value"]
                                                    ] = val["columns"].index(
                                                        item
                                                    )

                                        # Process rows for this table
                                        for row in val["source"]["body"][
                                            "Values"
                                        ]["rows"]:
                                            final_dict = {}

                                            for desired in desired_fields_list[
                                                table_idx
                                            ]:
                                                self._build_final_dict(
                                                    desired,
                                                    field_indexes[table_idx],
                                                    final_dict,
                                                    row,
                                                )

                                            all_tables_rows[table_idx].append(
                                                final_dict
                                            )

        return all_tables_rows

    @transaction.atomic
    def deserialize_academic_interests(self) -> None:
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
            new_array = phpload(stream)

            profile.academic_interests.clear()

            for item in new_array:
                # If the academic interest does not exist, create a new
                # instance of it. If it does exist, just add it to the
                # many-to-many field.
                profile.academic_interests.add(
                    AcademicInterest.objects.get_or_create(text=item)[0]
                )

            profile.save()

    def unescape(self, input_string: str) -> str:
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
                ["id", "user_login"],
                ["id", "type", "name", "field_order"],
                ["id", "field_id", "user_id", "value"],
            ],
            field_indexes=[
                {"id": 0, "user_login": 1},
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

            # delete profile's academic interests
            try:
                profile.academic_interests.clear()
            except AttributeError:
                pass

            # now get the data values for this user and add them to the model
            for data_value in data_values:
                if data_value["user_id"] == user["id"]:
                    for data_field in data_fields:
                        if data_field["id"] == data_value["field_id"]:
                            # unescape the value
                            if data_field["name"] == "Academic Interests":
                                interest, _ = (
                                    AcademicInterest.objects.get_or_create(
                                        text=data_value["value"]
                                    )
                                )
                                profile.academic_interests.add(interest)
                                break
                            elif data_field["name"] == "About":
                                profile.about_user = self.unescape(
                                    data_value["value"]
                                )
                                break
                            elif data_field["name"] == "Education":
                                profile.education = self.unescape(
                                    data_value["value"]
                                )
                                break
                            elif (
                                data_field["name"]
                                == "Upcoming Talks and Conferences"
                            ):
                                profile.upcoming_talks = data_value["value"]
                                break
                            elif data_field["name"] == "Projects":
                                profile.projects = data_value["value"]
                                break
                            elif data_field["name"] == "Publications":
                                profile.publications = data_value["value"]
                                break
                            elif data_field["name"] == "Site":
                                profile.site = data_value["value"]
                                break
                            elif (
                                data_field["name"]
                                == "Institutional or Other Affiliation"
                            ):
                                profile.institutional_or_other_affiliation = (
                                    data_value["value"]
                                )
                                break
                            elif data_field["name"] == "Title":
                                profile.title = data_value["value"]
                                break
                            elif data_field["name"] == "Figshare URL":
                                profile.figshare_url = data_value["value"]
                                break
                            elif data_field["name"] == "Name":
                                profile.name = data_value["value"]
                                break
                            elif data_field["name"] == "<em>ORCID</em> iD":
                                profile.orcid = data_value["value"]
                                break
                            elif data_field["name"] == "Mastodon handle":
                                profile.mastodon = data_value["value"]
                                break
                            else:
                                if data_field["name"] not in already_printed:
                                    rich.print(
                                        f'Unhandled field: "'
                                        f"{data_field['name']}\""
                                    )
                                    already_printed.append(data_field["name"])
                                break

            profile.save()

        self.deserialize_academic_interests()
