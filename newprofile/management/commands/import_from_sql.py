"""
A management command to import data from the SQL file
"""

import rich
from rich.progress import track, open
from sqloxide import parse_sql
from django.core.management.base import BaseCommand
from tqdm import tqdm

from newprofile.models import Profile, AcademicInterest
from newprofile.api import API


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

    def _parse_users(
        self, dump_filename, target_table, desired_fields, field_index=None
    ):
        """
        Parse the SQL dump for a given table and return rows of data in a
        generator.

        Args:
            dump_filename (str): The path to the SQL dump file
            target_table (str): The table to parse
            desired_fields (list): A list of fields to include in the output
            field_index (dict or None, optional): A pre-computed index of field
                names to their positions in the row. If not provided, will be
                computed. Defaults to None.
            generator (bool, optional): If True, returns a generator of rows.
                If False, returns a list of all rows. Defaults to True.

        Yields:
            dict: A dictionary of fields for each row in the table
        """
        if field_index is None:
            field_index = {}

        all_rows = []

        with open(dump_filename, "r", errors="ignore") as f:
            statement_counter = 0

            for line in f:
                try:
                    parser = parse_sql(line, dialect="mysql")
                except ValueError:
                    continue

                if len(parser) > 0:
                    for statement in parser:
                        if type(statement) is dict:
                            for key, val in statement.items():
                                if (
                                    key == "Insert"
                                    and val["table_name"][0]["value"]
                                    == target_table
                                ):
                                    statement_counter += 1

                                    # create an index of the fields once on the
                                    # first time. Assume it is the same from then
                                    # onwards
                                    if len(field_index) == 0:
                                        for item in val["columns"]:
                                            if item["value"] in desired_fields:
                                                field_index[item["value"]] = (
                                                    val["columns"].index(item)
                                                )

                                    for row in val["source"]["body"]["Values"][
                                        "rows"
                                    ]:
                                        final_dict = {}

                                        for desired in desired_fields:
                                            self._build_final_dict(
                                                desired,
                                                field_index,
                                                final_dict,
                                                row,
                                            )

                                        all_rows.append(final_dict)

        return all_rows

    def handle(self, *args, **options):

        rich.print("Parsing users...")
        users = self._parse_users(
            "/home/martin/hcprod.sql",
            "wp_users",
            [
                "id",
                "user_login",
            ],
            field_index={"id": 0, "user_login": 1},
        )

        rich.print("Parsing data fields...")
        data_fields = self._parse_users(
            "/home/martin/hcprod.sql",
            "wp_bp_xprofile_fields",
            ["id", "type", "name", "field_order"],
            field_index={"id": 0, "type": 3, "name": 4, "field_order": 8},
        )

        rich.print("Parsing data values...")
        data_values = self._parse_users(
            "/home/martin/hcprod.sql",
            "wp_bp_xprofile_data",
            ["id", "field_id", "user_id", "value"],
            field_index={"id": 0, "field_id": 1, "user_id": 2, "value": 3},
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
                            if data_field["name"] == "Academic Interests":
                                interest, _ = (
                                    AcademicInterest.objects.get_or_create(
                                        text=data_value["value"]
                                    )
                                )
                                profile.academic_interests.add(interest)
                            elif data_field["name"] == "About":
                                profile.about_user = data_value["value"]
                            elif data_field["name"] == "Education":
                                profile.education = data_value["value"]
                            elif (
                                data_field["name"]
                                == "Upcoming Talks and Conferences"
                            ):
                                profile.upcoming_talks = data_value["value"]
                            elif data_field["name"] == "Projects":
                                profile.projects = data_value["value"]
                            elif data_field["name"] == "Publications":
                                profile.publications = data_value["value"]
                            elif data_field["name"] == "Site":
                                profile.site = data_value["value"]
                            elif (
                                data_field["name"]
                                == "Institutional or Other Affiliation"
                            ):
                                profile.institutional_or_other_affiliation = (
                                    data_value["value"]
                                )
                            elif data_field["name"] == "Title":
                                profile.title = data_value["value"]
                            elif data_field["name"] == "Figshare URL":
                                profile.figshare_url = data_value["value"]
                            elif data_field["name"] == "Name":
                                profile.name = data_value["value"]
                            elif data_field["name"] == "<em>ORCID</em> iD":
                                profile.orcid = data_value["value"]

                            else:
                                if data_field["name"] not in already_printed:
                                    rich.print(
                                        f"Unhandled field: {data_field['name']}"
                                    )
                                    already_printed.append(data_field["name"])

            profile.save()
