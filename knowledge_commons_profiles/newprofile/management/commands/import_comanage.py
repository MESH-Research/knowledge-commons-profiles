"""
Import COManage roles into local models.

This allows us to retrieve COManage-style roles through this syntax:

roles:Role = Role.objects.get(person__user__username="martin_eve")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

# ruff: noqa: TC003
from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from pydantic import BaseModel
from pydantic import Field
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry

from knowledge_commons_profiles.newprofile.models import CO
from knowledge_commons_profiles.newprofile.models import Person
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.models import Role
from knowledge_commons_profiles.newprofile.models import RoleStatus

if TYPE_CHECKING:
    from collections.abc import Iterable


logger = logging.getLogger(__name__)


# =========================
# Pydantic response models
# =========================
class CoPerson(BaseModel):
    """
    Represents a single CoPerson record from COManage.
    """

    Version: str
    Id: str
    CoId: str
    Status: str
    Timezone: str | None = Field(default=None)
    Created: datetime
    Modified: datetime
    Revision: str
    Deleted: bool
    ActorIdentifier: str | None = Field(default=None)


class CoPeopleResponse(BaseModel):
    """
    Represents the full CoPeople API response.
    """

    ResponseType: str
    Version: str
    CoPeople: list[CoPerson]


class PersonRef(BaseModel):
    Type: str
    Id: str


# ruff: noqa: E741
class CoPersonRole(BaseModel):
    Version: str
    Id: str
    Person: PersonRef
    CouId: str
    Affiliation: str | None = None
    Title: str | None = None
    O: str | None = None
    Ou: str | None = None
    ValidThrough: str | None = None
    Status: str | None = None
    Created: str | None = None
    Modified: str | None = None
    Revision: str | None = None
    Deleted: bool | None = None
    ActorIdentifier: str | None = None
    SourceOrgIdentityId: str | None = None


class CoPersonRolesResponse(BaseModel):
    ResponseType: str
    Version: str
    CoPersonRoles: list[CoPersonRole]


# =========================
# HTTP client
# =========================


@dataclass
class ClientConfig:
    base_url: str
    token: str | None = None
    username: str | None = None
    password: str | None = None
    verify_ssl: bool = True
    timeout: int = 30


class COManageClient:
    """
    Minimal, resilient client for COmanage Registry API.
    """

    def __init__(self, cfg: ClientConfig) -> None:
        self.cfg = cfg
        self.session = requests.Session()

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.5,
            status_forcelist={429, 500, 502, 503, 504},
            allowed_methods={"GET"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        headers = {"Accept": "application/json"}
        if cfg.token:
            logger.info("Using Bearer token for authentication")
            headers["Authorization"] = f"Bearer {cfg.token}"
        else:
            logger.info("Using credentials for authentication")
        self.session.headers.update(headers)

    def _auth_kwargs(self) -> dict[str, Any]:
        if self.cfg.token:
            return {}
        if self.cfg.username and self.cfg.password:
            return {
                "username": self.cfg.username,
                "password": self.cfg.password,
            }
        return {}

    def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = (
            path
            if path.startswith("http")
            else urljoin(self.cfg.base_url.rstrip("/") + "/", path.lstrip("/"))
        )

        basic = HTTPBasicAuth(
            self._auth_kwargs()["username"], self._auth_kwargs()["password"]
        )

        resp = self.session.get(
            url,
            params=params or {},
            timeout=self.cfg.timeout,
            verify=self.cfg.verify_ssl,
            auth=basic,
        )
        try:
            payload = resp.json()
        except ValueError as ve:
            msg = (
                f"Non-JSON response from {url}: HTTP {resp.status_code} "
                f"{resp.text[:500]}"
            )
            raise CommandError(msg) from ve
        if resp.status_code >= HTTPStatus.BAD_REQUEST:
            msg = (
                f"Error from {url}: HTTP {resp.status_code} "
                f"{json.dumps(payload)[:500]}"
            )
            raise CommandError(msg)
        return payload

    def iter_roles(
        self,
    ) -> Iterable[tuple[CoPersonRole, CoPerson, Profile]]:
        """
        Iterate through roles. Endpoint path and
        parameters are configurable here.
        Adjust 'roles' path and parameter names to your COmanage deployment.
        """

        # get all users from our database
        logger.info("Fetching all users from the Profile database")
        users = Profile.objects.all()

        # for each user, get their COmanage person
        logger.info("Fetching COmanage people")
        for user in users:
            # get the user object
            msg = f"Fetching {user.username}"
            logger.info(msg)
            params = {"coid": 2, "search.identifier": user.username}
            try:
                co_person = self.get("co_people.json", params=params)
                co_person_obj = CoPeopleResponse.model_validate(co_person)
                co_person_obj = co_person_obj.CoPeople[0]

            except IndexError:
                msg = f"Error fetching COmanage person for {user.username}"
                logger.warning(msg)
                continue
            msg = f"Processing user {co_person_obj.Id}"
            logger.info(msg)

            # now get the roles
            params = {"copersonid": co_person_obj.Id}
            roles = self.get("co_person_roles.json", params=params)
            roles_obj = CoPersonRolesResponse.model_validate(roles)

            for role in roles_obj.CoPersonRoles:
                yield role, co_person_obj, user


# =========================
# Import logic
# =========================


def _norm_status(status: str | None) -> str:
    if not status:
        return RoleStatus.PENDING
    s = status.strip().lower().replace(" ", "_").replace("-", "_")
    # Map a few common variants
    aliases = {
        "ok": RoleStatus.ACTIVE,
        "approved": RoleStatus.ACTIVE,
        "pending_approval": RoleStatus.PENDING_APPROVAL,
        "pending_confirmation": RoleStatus.PENDING_CONFIRM,
        "grace": RoleStatus.GRACE_PERIOD,
        "grace_period": RoleStatus.GRACE_PERIOD,
    }
    return aliases.get(s, s if s in RoleStatus.values else RoleStatus.PENDING)


def _upsert_role(
    item: CoPersonRole,
    person: CoPerson,
    profile: Profile,
    *,
    dry_run: bool = False,
) -> tuple[Role, bool]:
    if not dry_run:
        person, _ = Person.objects.get_or_create(id=person.Id, user=profile)
    else:
        person = Person(id=person.Id, user=profile)

    if not dry_run:
        co, _ = CO.objects.get_or_create(id=item.CouId)
    else:
        co = CO(id=item.CouId)

    status = _norm_status(item.Status)

    defaults = {
        "co": co,
        "person": person,
        "affiliation": item.Affiliation,
        "status": status,
        "title": item.Title or "",
        "organization": item.O,
        "valid_through": item.ValidThrough,
        "source_system": "co-manage",
        "source_reference": item.SourceOrgIdentityId,
        "attributes": {},
    }

    # Uniqueness guard is coarse; align with your Role.Meta.constraints
    filters = {
        "person": person,
        "co": co,
        "source_system": defaults["source_system"],
        "source_reference": defaults["source_reference"],
    }

    if dry_run:
        # Build an unsaved instance to preview
        role = Role(**defaults)
        return role, True

    role, created = Role.objects.get_or_create(**filters, defaults=defaults)

    # If it already exists, update fields that may have changed
    if not created:
        changed = False
        for f in (
            "affiliation",
            "status",
            "title",
            "department",
            "organization",
            "sponsor",
            "valid_from",
            "valid_through",
            "enrollment_flow",
        ):
            new_val = defaults[f]
            if getattr(role, f) != new_val:
                setattr(role, f, new_val)
                changed = True
        if changed:
            role.full_clean()
            role.save()

    return role, created


# =========================
# Management command
# =========================


class Command(BaseCommand):
    help = (
        "Import Roles from a COmanage Registry instance "
        "(validated with Pydantic) and upsert into local models."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            default="https://registry.hcommons.org/",
            help="Base URL for COmanage Registry API "
            "(e.g., https://registry.hcommons.org/)",
        )
        parser.add_argument(
            "--token", default=None, help="Bearer token for API authentication"
        )
        parser.add_argument(
            "--username",
            default=None,
            help="Basic auth username (used if no token)",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Basic auth password (used if no token)",
        )
        parser.add_argument(
            "--no-verify-ssl",
            action="store_true",
            help="Disable SSL certificate verification (not recommended)",
        )
        parser.add_argument(
            "--since",
            default=None,
            help="Only fetch roles updated since this ISO timestamp "
            "(e.g., 2025-01-01T00:00:00Z) if supported by API",
        )
        parser.add_argument(
            "--per-page",
            type=int,
            default=200,
            help="Page size to request from API",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and log without writing to the database",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Import at most N roles (for testing)",
        )

    def handle(self, *args, **options):
        base_url: str = options["base_url"]
        token: str | None = options["token"]
        username: str | None = options["username"]
        password: str | None = options["password"]
        verify_ssl: bool = not options["no_verify_ssl"]
        dry_run: bool = options["dry_run"]
        limit: int | None = options["limit"]

        if not token and not (username and password):
            msg = (
                "Provide either --token OR both --username and "
                "--password for API authorization."
            )
            raise CommandError(msg)

        cfg = ClientConfig(
            base_url=base_url,
            token=token,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )
        client = COManageClient(cfg)

        total = 0
        created_count = 0
        updated_count = 0

        # Wrap the whole import in a transaction unless we're dry-running
        ctx = transaction.atomic() if not dry_run else _NullContext()

        try:
            with ctx:
                for item in client.iter_roles():
                    role: Role
                    role, created = _upsert_role(
                        item[0], item[1], item[2], dry_run=dry_run
                    )
                    if dry_run:
                        msg = f"Dry-run inserted {role}"
                        logger.info(msg)
                    total += 1
                    if created:
                        # created True in dry-run means "would create"
                        created_count += 1
                    else:
                        updated_count += 1

                    if total % 100 == 0:
                        self.stdout.write(f"Processed {total} roles...")

                    if limit and total >= limit:
                        break

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[DRY-RUN] Would process {total} roles "
                            f"(create: {created_count}, "
                            f"update: {updated_count})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Imported {total} roles "
                            f"(created: {created_count}, "
                            f"updated: {updated_count})"
                        )
                    )
        except CommandError:
            raise
        except Exception as e:
            msg = f"Import failed: {e}"
            raise CommandError(msg) from e


class _NullContext:
    def __enter__(self): ...
    def __exit__(self, exc_type, exc, tb): ...
