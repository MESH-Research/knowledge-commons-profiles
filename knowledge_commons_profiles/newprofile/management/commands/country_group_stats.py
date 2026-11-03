"""
Print member counts for a named group of countries

The counts come from the most recent UserStats row written by build_stats,
which records the country of each member's ROR-matched institution. Members
without a matched institution therefore do not appear.
"""

import json

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from rich import box
from rich.console import Console
from rich.table import Table

from knowledge_commons_profiles.newprofile.country_groups import COUNTRY_GROUPS
from knowledge_commons_profiles.newprofile.country_groups import GROUP_ALIASES
from knowledge_commons_profiles.newprofile.country_groups import (
    UnknownGroupError,
)
from knowledge_commons_profiles.newprofile.country_groups import (
    group_member_counts,
)
from knowledge_commons_profiles.newprofile.country_groups import resolve_group
from knowledge_commons_profiles.newprofile.models import UserStats


def load_country_counts() -> dict[str, int] | None:
    """
    Read the ISO code -> member count map from the latest stats row

    :return: the counts, or None if build_stats has never been run
    """
    stats = UserStats.objects.order_by("-pk").first()

    if stats is None:
        return None

    return json.loads(stats.countries or "{}")


def build_group_table(
    group_name: str,
    rows: list[tuple[str, str, int]],
    group_size: int,
) -> Table:
    """
    Lay out a group's member counts as a Rich table

    :param group_name: the canonical group name for the title
    :param rows: (code, country name, count) tuples in display order
    :param group_size: how many countries make up the group in total
    """
    total = sum(count for _, _, count in rows)
    represented = sum(1 for _, _, count in rows if count > 0)

    table = Table(
        title=f"[bold]{group_name}[/bold]  ·  members by country",
        caption=(
            f"{represented} of {group_size} countries in this group have "
            "members. Counts are of members with a ROR-matched institution."
        ),
        box=box.ROUNDED,
        show_footer=True,
        header_style="bold cyan",
        footer_style="bold",
        title_style="",
        caption_style="dim",
    )

    table.add_column("#", justify="right", style="dim", footer="")
    table.add_column("Country", footer="Total", no_wrap=True)
    table.add_column("ISO", justify="center", style="dim", footer="")
    table.add_column(
        "Members", justify="right", style="magenta", footer=f"{total:,}"
    )
    table.add_column("Share", justify="right", style="green", footer="100%")

    for rank, (code, name, count) in enumerate(rows, start=1):
        share = (count / total * 100) if total else 0
        table.add_row(
            str(rank),
            name,
            code,
            f"{count:,}",
            f"{share:.1f}%",
        )

    return table


def build_groups_table() -> Table:
    """
    List every available group with its size and aliases
    """
    aliases: dict[str, list[str]] = {}
    for alias, canonical in GROUP_ALIASES.items():
        aliases.setdefault(canonical, []).append(alias)

    table = Table(
        title="[bold]Available country groups[/bold]",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="",
    )
    table.add_column("Group", no_wrap=True)
    table.add_column("Countries", justify="right", style="magenta")
    table.add_column("Also known as", style="dim")

    for name, codes in COUNTRY_GROUPS.items():
        table.add_row(
            name, str(len(codes)), ", ".join(sorted(aliases.get(name, [])))
        )

    return table


class Command(BaseCommand):
    """
    Print member counts for a named group of countries
    """

    help = (
        "Print a table of member counts for the countries in a named group, "
        'e.g. "Global South", "Anglophone", "Europe" or "Indo-China". '
        "Use --list to see every group."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "group",
            nargs="*",
            help="The group name (quotes optional; words are joined)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List the available groups instead of printing counts",
        )
        parser.add_argument(
            "--show-zero",
            action="store_true",
            help="Include countries in the group that have no members",
        )

    def handle(self, *args, **options):
        console = Console(file=self.stdout)

        if options["list"]:
            console.print(build_groups_table())
            return

        requested = " ".join(options["group"]).strip()

        if not requested:
            msg = (
                "Please name a country group, e.g. "
                '"Global South". Use --list to see the available groups.'
            )
            raise CommandError(msg)

        try:
            group_name, codes = resolve_group(requested)
        except UnknownGroupError as exc:
            msg = (
                f'Unknown country group "{requested}". '
                "Use --list to see the available groups."
            )
            raise CommandError(msg) from exc

        counts = load_country_counts()

        if counts is None:
            msg = "No stats have been built yet. Run build_stats first."
            raise CommandError(msg)

        rows = group_member_counts(
            codes, counts, include_zero=options["show_zero"]
        )

        console.print(build_group_table(group_name, rows, len(codes)))
