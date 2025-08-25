from contextlib import contextmanager
from simple_history import signals as history_signals


HISTORY_SIGNALS = [
    history_signals.pre_create_historical_record,
    history_signals.post_create_historical_record,
    history_signals.pre_create_historical_m2m_records,
    history_signals.post_create_historical_m2m_records,
]


@contextmanager
def disable_all_signals():
    backups = {}

    # سیگنال‌ها رو خالی کن
    for sig in HISTORY_SIGNALS:
        backups[sig] = sig.receivers[:]
        sig.receivers.clear()

    try:
        yield
    finally:
        # برگردوندن سیگنال‌ها
        for sig, recs in backups.items():
            sig.receivers[:] = recs
