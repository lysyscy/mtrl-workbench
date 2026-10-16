"""Account identity checks exposed to other business modules."""
from app.mod15_user import domain as D, repository as R


def active_account(session, identity):
    row = R.by_identity(session, identity)
    return row if row is not None and row.status == D.STATUS_ACTIVE and not D.is_deleted(row) else None
