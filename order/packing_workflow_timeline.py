"""Build read-only Packing workflow timelines from persisted WorkFlow records.

Transition records store the source state in `state` and the destination in
`current_state_name`. Assignment changes are *not* new stage entries.
"""
from datetime import timedelta


ACTION_LABELS = {
    1: 'پیش‌نویس',
    2: 'بازگشت به مرحله قبل',
    3: 'ارسال به مرحله بعد',
    4: 'تغییر مسئول',
    5: 'ایجاد پکینگ',
}


def format_elapsed(delta):
    """Human-readable duration without rounding incomplete minutes upward."""
    if delta is None:
        return None
    seconds = max(0, int(delta.total_seconds()))
    days, remaining = divmod(seconds, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes = remaining // 60
    parts = []
    if days:
        parts.append(f'{days} روز')
    if hours:
        parts.append(f'{hours} ساعت')
    if minutes or not parts:
        parts.append(f'{minutes} دقیقه')
    return ' و '.join(parts)


def build_packing_workflow_timeline(records, states, normalize_state):
    """Return timeline stages and complete activity history.

    Each completed connector shows the *latest actual forward transition* from
    that exact state to its next state, not a guessed subtraction of two
    unrelated dates. This matters when users go back and progress again.
    """
    stages = list(states or [])
    entries = {}
    forward_durations = {}
    history = []
    previous_event_date = None

    for event in records:
        status = event.wf_status
        source = normalize_state(event.state)
        target = normalize_state(event.current_state_name)

        if not target and source in stages:
            index = stages.index(source)
            if status == 3 and index + 1 < len(stages):
                target = stages[index + 1]
            elif status == 2 and index > 0:
                target = stages[index - 1]
            else:
                target = source

        created_at = event.created_date

        if (
            status == 3
            and source in stages
            and target in stages
            and stages.index(target) == stages.index(source) + 1
            and source in entries
            and created_at is not None
            and created_at >= entries[source]
        ):
            forward_durations[source] = created_at - entries[source]

        # Only stage transitions and the initial creation count as entries.
        if status in (2, 3, 5) and target in stages and created_at:
            entries[target] = created_at

        action_duration = (
            created_at - previous_event_date
            if previous_event_date and created_at and created_at >= previous_event_date
            else None
        )
        history.append({
            'created_at': created_at,
            'status': status,
            'action': ACTION_LABELS.get(status, event.action or 'رویداد'),
            'source': source or None,
            'target': target or None,
            'actor': event.from_user or event.creator_user,
            'assigned_to': event.to_user,
            'description': event.wf_description or '',
            'elapsed_since_previous': format_elapsed(action_duration),
        })
        if created_at is not None:
            previous_event_date = created_at

    stage_data = []
    for index, name in enumerate(stages):
        elapsed = forward_durations.get(name) if index < len(stages) - 1 else None
        stage_data.append({
            'name': name,
            'index': index,
            'entered_at': entries.get(name),
            'duration_to_next': format_elapsed(elapsed),
        })

    return {'stages': stage_data, 'history': list(reversed(history))}
