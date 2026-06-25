"""Legacy backfill use-case service (Phase 2.3): import the pre-rebuild data.

PURE: stdlib + ``domain`` only. Depends on the
:class:`~downlow.domain.ports.Repository` *port* for the entities it writes
(:class:`User`, :class:`ResearchProfileRecord`, :class:`OutputProfileRecord`); the
concrete SQLModel repos are injected at the composition root (``cli/deps.py``). This
service never reads a file -- the CLI/composition root parses the legacy JSON tree
and hands this service plain :class:`LegacyImport` data, so ``core`` stays testable
without the real ``legacy/`` directory.

The headline is **idempotency**: this is a one-shot data migration the owner may run
more than once (a partial run, a re-run after fixing a profile), so every import is
an upsert keyed on a stable identity -- re-running imports nothing twice.

Dedupe keys (the locked identity of each imported row):

* :class:`User` -- by ``username`` (the legacy ``users/<name>`` directory name and
  the ``research_data.json`` per-user key are the same handle). The default owner
  (``luke`` / id 1) is already seeded by the processing composition root; the
  backfill resolves it and adds any *other* legacy user it finds.
* :class:`ResearchProfileRecord` -- one active profile **per user** (the data model
  states ``user_id`` is unique per user). So the dedupe key is ``user_id``: a user
  already carrying a research profile is left untouched (no overwrite, no duplicate).
* :class:`OutputProfileRecord` -- by ``(user_id, name)``. The legacy
  ``document_data.json`` is a single *global* profile (it has no per-user key and no
  name), so it is imported as one named ``"default"`` output profile per user.

The orphan legacy audio (a ``users/<name>/audio/*.mp3`` with no source PDF and no
summary present) is **deliberately not imported** by this service. Registering it
would require fabricating a placeholder :class:`Paper` with an empty
``source_pdf_ref`` / ``source_hash`` and a :class:`Summary`-less, sourceless
:class:`Episode` -- a row that lies about having a source the pipeline could
re-derive, and that the dedupe machinery (keyed on ``source_hash``) cannot safely
re-resolve. The mp3 is instead **reported** as a skipped orphan (path + reason) so
the owner can re-ingest the real PDF through ``dl process``, which rebuilds the
podcast properly. See :class:`BackfillReport`. (The choice is recorded here so a
later phase that *does* want to shelve orphan audio has the rationale.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from downlow.domain.entities import OutputProfileRecord, ResearchProfileRecord, User
from downlow.domain.ports import Repository

# The name given to the single global legacy output profile when imported per user.
_DEFAULT_OUTPUT_PROFILE_NAME = "default"


@dataclass(frozen=True)
class LegacyResearchProfile:
    """One user's research identity parsed from ``data/research_data.json``.

    ``username`` is the legacy per-user key (``luke`` / ``harriet`` / ``mehrnia``);
    it both identifies the owning :class:`User` and is that user's directory name in
    the ``legacy/users/`` tree. Pure value object so the CLI can parse the JSON and
    hand it in without this service touching the filesystem.
    """

    username: str
    research_field: str = ""
    research_topic: str = ""
    research_interests: tuple[str, ...] = ()
    research_focus: str = ""


@dataclass(frozen=True)
class LegacyOutputProfile:
    """The (global) output shaping parsed from ``data/document_data.json``.

    Legacy ``document_data.json`` is a single document profile shared by every user
    (no per-user key, no name), so it is applied to each imported user under the name
    ``"default"``. Pure value object (no file IO in ``core``).
    """

    document_type: str = ""
    return_details: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegacyOrphanAudio:
    """A ``users/<name>/audio/*.mp3`` with no source PDF / summary in the tree.

    Carried through to the :class:`BackfillReport` as a *skipped* orphan (it is never
    written to the DB -- see the module docstring for why a placeholder Paper is
    wrong). ``owner`` is the user whose tree it sat in; ``path`` is its absolute
    location for the report.
    """

    owner: str
    path: str


@dataclass(frozen=True)
class LegacyImport:
    """The parsed legacy dataset handed to :meth:`BackfillService.run`.

    Assembled by the composition root from the on-disk ``legacy/`` tree. ``users`` is
    the set of usernames discovered across BOTH ``research_data.json`` and the
    ``users/`` directory tree (their union -- a user may appear in one but not the
    other). Keeping all parsing in the caller leaves this a pure-data argument.
    """

    users: tuple[str, ...] = ()
    research_profiles: tuple[LegacyResearchProfile, ...] = ()
    output_profile: LegacyOutputProfile | None = None
    orphan_audio: tuple[LegacyOrphanAudio, ...] = ()


@dataclass
class BackfillReport:
    """The outcome of a backfill run: what was imported, skipped, already present.

    Every counter distinguishes *imported* (a new row written this run) from
    *already present* (an idempotent no-op -- the row existed from a prior run or the
    composition-root seed). ``skipped_orphan_audio`` lists the orphan mp3s that were
    deliberately not imported, each with the reason, so the CLI can surface them.
    """

    users_imported: int = 0
    users_already_present: int = 0
    research_profiles_imported: int = 0
    research_profiles_already_present: int = 0
    output_profiles_imported: int = 0
    output_profiles_already_present: int = 0
    skipped_orphan_audio: list[LegacyOrphanAudio] = field(default_factory=list)


class BackfillService:
    """Import the legacy JSON profiles + users tree into the DB (idempotently).

    Pure ``core`` over the :class:`Repository` port: the SQLite-now / Postgres-later
    switch and all file IO live outside it.
    """

    def __init__(
        self,
        *,
        users: Repository[User],
        research_profiles: Repository[ResearchProfileRecord],
        output_profiles: Repository[OutputProfileRecord],
    ) -> None:
        """Wire the service.

        Args:
            users: repository for :class:`User` rows.
            research_profiles: repository for :class:`ResearchProfileRecord` rows.
            output_profiles: repository for :class:`OutputProfileRecord` rows.
        """
        self._users = users
        self._research_profiles = research_profiles
        self._output_profiles = output_profiles

    def run(self, data: LegacyImport) -> BackfillReport:
        """Import ``data`` into the DB; return a :class:`BackfillReport`.

        Idempotent end to end: each entity is upserted on its dedupe key, so a
        re-run imports nothing twice. Order matters -- users first (research /
        output profiles carry a ``user_id`` FK), then per-user profiles, then the
        orphan-audio report.
        """
        report = BackfillReport()

        # 1) Users -- the union of the JSON keys + the users/ tree, each upserted by
        # username. Build a username -> id map for the profile FKs below.
        user_ids: dict[str, int] = {}
        for username in _ordered_unique(data.users):
            user, created = self._ensure_user(username)
            if user.id is None:  # pragma: no cover - the repository always assigns an id
                raise RuntimeError("repository did not assign a user id")
            user_ids[username] = user.id
            if created:
                report.users_imported += 1
            else:
                report.users_already_present += 1

        # 2) Research profiles -- one per user, deduped on user_id.
        for profile in data.research_profiles:
            user_id = user_ids.get(profile.username)
            if user_id is None:
                # A profile for a user not in the union is impossible (the union
                # includes every research-profile username), but guard defensively.
                user, _created = self._ensure_user(profile.username)
                if user.id is None:  # pragma: no cover - the repository always assigns an id
                    raise RuntimeError("repository did not assign a user id")
                user_id = user.id
                user_ids[profile.username] = user_id
            if self._import_research_profile(user_id, profile):
                report.research_profiles_imported += 1
            else:
                report.research_profiles_already_present += 1

        # 3) The single global output profile -- applied to every imported user as a
        # named "default", deduped on (user_id, name).
        if data.output_profile is not None:
            for user_id in user_ids.values():
                if self._import_output_profile(user_id, data.output_profile):
                    report.output_profiles_imported += 1
                else:
                    report.output_profiles_already_present += 1

        # 4) Orphan audio -- never imported; reported as a deliberate skip.
        report.skipped_orphan_audio = list(data.orphan_audio)

        return report

    # --- internals ----------------------------------------------------------- #

    def _ensure_user(self, username: str) -> tuple[User, bool]:
        """Return the user with ``username``, inserting it if absent.

        Returns ``(user, created)`` -- ``created`` is ``True`` only when this call
        inserted the row. Deduped on ``username`` (the legacy handle), so the default
        owner already seeded by the processing composition root resolves rather than
        duplicating.
        """
        existing = self._find_user(username)
        if existing is not None:
            return existing, False
        created = self._users.add(User(username=username, display_name=username.capitalize()))
        return created, True

    def _find_user(self, username: str) -> User | None:
        """Find a user by its unique ``username`` (the dedupe key)."""
        matches = self._users.list(username=username)
        return matches[0] if matches else None

    def _import_research_profile(self, user_id: int, profile: LegacyResearchProfile) -> bool:
        """Insert ``profile`` for ``user_id`` if the user has none yet.

        Returns ``True`` when a row was inserted, ``False`` when the user already
        carried a research profile (the dedupe key is ``user_id`` -- one active
        profile per user, no overwrite of an existing one).
        """
        if self._research_profiles.list(user_id=user_id):
            return False
        self._research_profiles.add(
            ResearchProfileRecord(
                user_id=user_id,
                research_field=profile.research_field,
                research_topic=profile.research_topic,
                research_interests=list(profile.research_interests),
                research_focus=profile.research_focus,
            )
        )
        return True

    def _import_output_profile(self, user_id: int, profile: LegacyOutputProfile) -> bool:
        """Insert the global output profile for ``user_id`` under ``"default"`` if absent.

        Returns ``True`` when a row was inserted, ``False`` when this user already has
        a ``(user_id, "default")`` output profile (the dedupe key).
        """
        if self._output_profiles.list(user_id=user_id, name=_DEFAULT_OUTPUT_PROFILE_NAME):
            return False
        self._output_profiles.add(
            OutputProfileRecord(
                user_id=user_id,
                name=_DEFAULT_OUTPUT_PROFILE_NAME,
                document_type=profile.document_type,
                return_details=list(profile.return_details),
            )
        )
        return True


def _ordered_unique(items: tuple[str, ...]) -> list[str]:
    """De-duplicate ``items`` preserving first-seen order (stable, deterministic)."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
