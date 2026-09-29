"""
Automatic ORIGINAL/BASELINE capture.

Two SQLAlchemy ``after_insert`` hooks guarantee the Original view of
hardware state exists no matter which code path creates the data (Setup
API, Excel import, seed script, tests, ...), instead of relying on each
creation path to remember to snapshot it:

  * a new ``Setup`` row  -> one ``SetupHardwareBaseline`` row holding the
    fixed hardware fields exactly as they were at creation;
  * a new ``SetupCustomFieldValue`` row -> one ``SetupCustomFieldBaseline``
    row holding that first value (skipped if a baseline for that
    setup/column already exists, e.g. captured by a Swap beforehand).

Both hooks only ever INSERT; baselines are never updated afterwards.
The hooks use the flush's own connection (the documented pattern for
mapper events), so they participate in the same transaction.
"""
from sqlalchemy import event, select

from app.models.setup import Setup
from app.models.setup_custom_field_baseline import SetupCustomFieldBaseline
from app.models.setup_custom_field_value import SetupCustomFieldValue
from app.models.setup_hardware_baseline import BASELINE_FIELD_NAMES, SetupHardwareBaseline


@event.listens_for(Setup, "after_insert")
def _capture_hardware_baseline(mapper, connection, target):  # noqa: ANN001
    table = SetupHardwareBaseline.__table__
    if connection.execute(select(table.c.id).where(table.c.setup_id == target.id)).first() is not None:
        return
    values = {name: getattr(target, name, None) for name in BASELINE_FIELD_NAMES}
    connection.execute(table.insert().values(setup_id=target.id, **values))


@event.listens_for(SetupCustomFieldValue, "after_insert")
def _capture_custom_baseline(mapper, connection, target):  # noqa: ANN001
    table = SetupCustomFieldBaseline.__table__
    existing = connection.execute(
        select(table.c.id).where(
            table.c.setup_id == target.setup_id, table.c.template_column_id == target.template_column_id
        )
    ).first()
    if existing is not None:
        return
    connection.execute(
        table.insert().values(
            setup_id=target.setup_id, template_column_id=target.template_column_id, value=target.value
        )
    )
