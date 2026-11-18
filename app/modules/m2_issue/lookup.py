"""旧号查卷：保留当年归档，同时带出修订后的分卷。"""
from app.errors import DomainError
from app.reasons import REASONS
from app.store import get_archive, get_revision


def lookup_edition(issue: str, edition: str) -> dict:
    archive = get_archive(issue, edition)
    revision = get_revision(issue, edition)
    if archive is None and revision is None:
        raise DomainError("UNKNOWN_REFERENCE", REASONS["UNKNOWN_REFERENCE"])

    volumes = []
    if revision is not None:
        for volume in revision["volumes"]:
            volume_archive = get_archive(issue, volume["edition"])
            volumes.append({
                "edition": volume["edition"],
                "expected_pages": volume["expected_pages"],
                "status": volume_archive["status"] if volume_archive else "revised",
            })
    current_editions = [each["edition"] for each in volumes] if revision else [edition]
    return {
        "issue": issue,
        "query_edition": edition,
        "revised": revision is not None,
        "revision_id": revision["revision_id"] if revision else None,
        "archive": archive,
        "volumes": volumes,
        "current_editions": current_editions,
    }
