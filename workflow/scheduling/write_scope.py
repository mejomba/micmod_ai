"""Narrow transaction-local permission for internal scheduling services.

These settings prevent accidental bypass via ordinary ORM writes and direct SQL.
They are not a security boundary against someone with privileged database access.
"""
from contextlib import contextmanager
from django.db import connection, transaction


@contextmanager
def scheduling_write_scope(operation, object_id):
    if operation not in ('publish', 'detail_revision'):
        raise ValueError('Unknown scheduling write operation.')
    if type(object_id) is not int or object_id <= 0:
        raise ValueError('A persisted scheduling object is required.')
    key = 'portal.scheduling_' + operation
    with transaction.atomic():
        if connection.vendor != 'postgresql':
            yield
            return
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_setting(%s, true)', [key])
            previous = cursor.fetchone()[0] or ''
            cursor.execute('SELECT set_config(%s, %s, true)', [key, str(object_id)])
        # On an exception the savepoint/transaction rolls back the local
        # setting, even if the database transaction is marked broken.
        yield
        with connection.cursor() as cursor:
            cursor.execute('SELECT set_config(%s, %s, true)', [key, previous])
