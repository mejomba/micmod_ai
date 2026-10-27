"""Presentation helpers for Packing/PackingItem's existing ChangeLog records.

The inherited NoUserBaseModel.save() already persists `diff_json.fields`
as [new_value, old_value]. Keep the audit trail in ChangeLog rather than
creating a parallel history table.
"""
from django.utils.text import capfirst


def _value(value):
    if value is None or value == '':
        return '—'
    if isinstance(value, bool):
        return 'بله' if value else 'خیر'
    return str(value)


def _field_labels(model):
    labels = {}
    for field in model._meta.fields:
        label = capfirst(str(field.verbose_name))
        labels[field.name] = label
        labels[field.attname] = label
    return labels


def build_packing_change_history(logs, packing_model, item_model, item_rows):
    """Render old/new audit snapshots with user, timestamp, and row identity.

    `item_rows` contains even soft-deleted PackingItem records; otherwise the
    audit history would hide deleted rows. No log data is modified.
    """
    item_names = {}
    for row in item_rows:
        pk = row['id']
        order_number = row.get('order__order_number') or row.get('order_id')
        part = row.get('part_number')
        label = f'ردیف {pk}'
        if order_number:
            label += f' · سفارش {order_number}'
        if part:
            label += f' · {part}'
        item_names[pk] = label

    header_labels = _field_labels(packing_model)
    item_labels = _field_labels(item_model)
    history = []

    for log in logs:
        # content_type is loaded by select_related in the view.
        is_item = log.content_type.model == item_model._meta.model_name
        field_labels = item_labels if is_item else header_labels
        raw_fields = (log.diff_json or {}).get('fields') or {}
        changes = []
        for key, values in raw_fields.items():
            if key in ('editor_user_id', 'creator_user_id'):
                # User attribution is already in the event header.
                continue
            if isinstance(values, (list, tuple)):
                new_value = values[0] if values else None
                old_value = values[1] if len(values) > 1 else None
            else:
                new_value, old_value = values, None

            if log.action != 1 and new_value == old_value:
                continue
            changes.append({
                'key': key,
                'label': field_labels.get(key, key),
                'old': _value(old_value),
                'new': _value(new_value),
            })

        soft_deleted = is_item and (
            isinstance(raw_fields.get('is_deleted'), (list, tuple))
            and raw_fields['is_deleted'][0] is True
            and raw_fields['is_deleted'][1] is False
        )
        action = 'delete' if soft_deleted or log.action == 3 else (
            'create' if log.action == 1 else 'update'
        )
        if not changes and action == 'update':
            continue

        history.append({
            'id': log.pk,
            'created_at': log.created_date,
            'actor': log.editor_user or log.creator_user,
            'scope': 'item' if is_item else 'packing',
            'target': item_names.get(log.object_id, f'ردیف {log.object_id}') if is_item else 'سربرگ پکینگ',
            'action': action,
            'changes': changes,
        })

    return history
