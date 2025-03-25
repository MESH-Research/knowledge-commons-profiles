"""
A management command to import data from the SQL file
"""

import contextlib

# pylint: disable=import-error,no-name-in-module,too-many-arguments
# pylint: disable=too-many-positional-arguments,no-member
import rich
from django.core.management.base import BaseCommand
from django.db import transaction
from rich.progress import track
from smart_open import open  # noqa: A004 (allow shadow of builtin)
from sqloxide import parse_sql

from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile


class Command(BaseCommand):
    """
    A management command to import data from the SQL file
    """

    help = "Import data from SQL into the Profile model"

    # the fields we want to grab
    # the boolean value refers to whether or not an "unescape" will be
    # performed on the field
    DATA_MATCHES = {
        "About": ("about_user", True),
        "Education": ("education", True),
        "Upcoming Talks and Conferences": ("upcoming_talks", True),
        "Publications": ("publications", True),
        "Projects": ("projects", True),
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
        "<em>Twitter</em> handle": ("twitter", False),
        "CV": ("cv", False),
        "Memberships": ("commons_groups", True),
        "LinkedIn URL": ("linkedin", False),
        "Website URL": ("website", False),
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

        with open(dump_filename, "r", errors="ignore") as f:
            statement_counters = [0 for _ in target_tables]

            for line in track(f):
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

    def _parse_data(  # noqa: PLR0913
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

    def _handle_insert(  # noqa: PLR0913
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
    def _build_index(  # noqa: PLR0913
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
            "unicode-escape",
        )

    def add_arguments(self, parser):
        parser.add_argument(
            "-file", type=str, default="/home/martin/hcprod.sql"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        """
        This command imports a MySQL dump file into the Django database.
        """

        rich.print("Parsing tables from SQL file...")

        (
            users,
            data_fields,
            data_values,
            wp_term_relationships,
            wp_term_taxonomy,
            wp_terms,
        ) = self._parse_multiple_tables(
            dump_filename=options["file"],  # "/home/martin/hcprod.sql",
            target_tables=[
                "wp_users",
                "wp_bp_xprofile_fields",
                "wp_bp_xprofile_data",
                "wp_term_relationships",
                "wp_term_taxonomy",
                "wp_terms",
            ],
            desired_fields_list=[
                ["id", "user_login", "user_email", "user_registered"],
                ["id", "type", "name", "field_order"],
                ["id", "field_id", "user_id", "value"],
                ["object_id", "term_taxonomy_id"],
                ["term_taxonomy_id", "term_id", "taxonomy"],
                ["term_id", "name"],
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
                {"object_id": 0, "term_taxonomy_id": 1},
                {"term_taxonomy_id": 0, "term_id": 1, "taxonomy": 2},
                {"term_id": 0, "name": 1},
            ],
        )

        already_printed = []

        for user in track(users):
            # get the model
            profile, _ = Profile.objects.get_or_create(
                username=user["user_login"],
            )
            profile.central_user_id = user["id"]
            profile.email = user["user_email"]

            # delete profile's academic interests
            with contextlib.suppress(AttributeError):
                profile.academic_interests.clear()

            # now get the data values for this user and add them to the model
            for data_value in data_values:
                self._handle_values(
                    already_printed,
                    data_fields,
                    data_value,
                    profile,
                    user,
                    wp_term_relationships,
                    wp_term_taxonomy,
                    wp_terms,
                )

            profile.save()

    def _handle_values(  # noqa: PLR0913
        self,
        already_printed,
        data_fields,
        data_value,
        profile,
        user,
        wp_term_relationships,
        wp_term_taxonomy,
        wp_terms,
    ):
        if data_value["user_id"] == user["id"]:
            for data_field in data_fields:
                if data_field["id"] == data_value["field_id"]:
                    if data_field["name"] == "Academic Interests":
                        # academic interests are nested deep in the taxonomy
                        # system of WordPress, which is a bit of a labyrinth
                        self._handle_academic_interests(
                            profile,
                            user,
                            wp_term_relationships,
                            wp_term_taxonomy,
                            wp_terms,
                        )
                    elif data_field["name"] in self.DATA_MATCHES:
                        # if the data field has a match in the DATA_MATCHES
                        # and it has the value of the second field set to True
                        # then escape it. Put the value into the associated
                        # field of profile.
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
                            f'Unhandled field: "{data_field["name"]}"',
                        )
                        already_printed.append(data_field["name"])

    def _handle_academic_interests(
        self,
        profile,
        user,
        wp_term_relationships,
        wp_term_taxonomy,
        wp_terms,
    ):
        """
        Handles the academic interests for a user.

        This method takes a user object, the set of term relationships,
        the set of term taxonomies, and the set of terms as input and
        processes the academic interests for the user.

        Academic interests are stored in the `wp_term_relationships`
        table, which contains object IDs, term IDs, and taxonomy IDs.
        The taxonomy ID is used to link the term to a taxonomy, and
        the term ID is used to link the term to the `wp_terms` table,
        which contains the name of the term.

        The academic interests are then stored in the `academic_interests`
        field of the user's profile object.

        :param profile: The profile object associated with the user
        :type profile: Profile
        :param user: The user object
        :type user: dict
        :param wp_term_relationships: The set of term relationships
        :type wp_term_relationships: list
        :param wp_term_taxonomy: The set of term taxonomies
        :type wp_term_taxonomy: list
        :param wp_terms: The set of terms
        :type wp_terms: list
        """
        for term_relationship in wp_term_relationships:
            if term_relationship["object_id"] == user["id"]:
                for term_taxonomy in wp_term_taxonomy:
                    self._handle_wp_term_taxonomy(
                        profile,
                        term_relationship,
                        term_taxonomy,
                        wp_terms,
                    )

    def _handle_wp_term_taxonomy(
        self,
        profile,
        term_relationship,
        term_taxonomy,
        wp_terms,
    ):
        """
        Add AcademicInterests to a Profile, given a term relationship and its
        taxonomy.

        Parameters
        ----------
        profile : Profile
            The Profile to which the AcademicInterests should be added
        term_relationship : dict
            A dictionary representing a term relationship in the WordPress
            taxonomy
        term_taxonomy : dict
            A dictionary representing the taxonomy of a term in WordPress
        wp_terms : list
            A list of dictionaries representing the terms in the WordPress
            taxonomy

        Returns
        -------
        None
        """
        if (
            term_taxonomy["term_taxonomy_id"]
            == term_relationship["term_taxonomy_id"]
            and term_taxonomy["taxonomy"] == "mla_academic_interests"
        ):
            for term in wp_terms:
                self._handle_wp_terms(profile, term, term_taxonomy)

    @staticmethod
    def _handle_wp_terms(profile, term, term_taxonomy):
        """
        Add an AcademicInterest to a Profile, given a term and its taxonomy.

        Parameters
        ----------
        profile : Profile
            The Profile to which the AcademicInterest should be added
        term : dict
            A dictionary representing a term in the WordPress taxonomy
        term_taxonomy : dict
            A dictionary representing the taxonomy of a term in WordPress

        Returns
        -------
        None
        """
        if term["term_id"] == term_taxonomy["term_id"]:
            interest, _ = AcademicInterest.objects.get_or_create(
                text=term["name"],
            )
            profile.academic_interests.add(interest)
