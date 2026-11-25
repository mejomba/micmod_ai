"""Protect published policy versions and persisted revisions in PostgreSQL.

Only scheduling tables are affected. No historical data is rewritten.
"""
from django.db import migrations

POLICY = 'workflow_workflowschedulepolicy'
CONFIG = {
    'workflow_workflowcalendar': 'policy_id',
    'workflow_workflowcalendarexception': 'calendar_id',
    'workflow_workflowstagetiming': 'policy_id',
    'workflow_workflowtimingrule': 'stage_timing_id',
    'workflow_workflowscheduletransition': 'policy_id',
}
FORECAST = 'workflow_workflowforecast'
DETAILS = ('workflow_workflowforecaststep', 'workflow_workflowforecastanchor')

SQL = """
CREATE FUNCTION wf_sched_guard_policy() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
            RAISE EXCEPTION 'Create a draft and publish through the policy service' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status <> 'draft' THEN
        IF TG_OP = 'UPDATE' THEN
            -- Permit only nullable audit-user references to be cleared by
            -- the user deletion collector; all scheduling data stays intact.
            IF (to_jsonb(OLD) - 'created_by_id' - 'published_by_id')
                = (to_jsonb(NEW) - 'created_by_id' - 'published_by_id')
                AND (NEW.created_by_id IS NULL OR NEW.created_by_id IS NOT DISTINCT FROM OLD.created_by_id)
                AND (NEW.published_by_id IS NULL OR NEW.published_by_id IS NOT DISTINCT FROM OLD.published_by_id)
            THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Published scheduling policy is immutable' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF (NEW.workflow_key, NEW.code, NEW.version) IS DISTINCT FROM
       (OLD.workflow_key, OLD.code, OLD.version) THEN
        RAISE EXCEPTION 'Policy family and version are immutable' USING ERRCODE = '23514';
    END IF;
    IF NEW.status <> 'draft' AND (
        NEW.status <> 'published' OR
        current_setting('portal.scheduling_publish', true) IS DISTINCT FROM OLD.id::text
    ) THEN
        RAISE EXCEPTION 'Use the validated policy publication service' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $;

CREATE FUNCTION wf_sched_guard_config() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    old_parent bigint;
    new_parent bigint;
    old_policy bigint;
    new_policy bigint;
    parent_status text;
    locked_id bigint;
    calendar_policy bigint;
BEGIN
    IF TG_OP <> 'INSERT' THEN old_parent := (to_jsonb(OLD)->>TG_ARGV[0])::bigint; END IF;
    IF TG_OP <> 'DELETE' THEN new_parent := (to_jsonb(NEW)->>TG_ARGV[0])::bigint; END IF;
    IF TG_ARGV[0] = 'calendar_id' THEN
        SELECT policy_id INTO old_policy FROM workflow_workflowcalendar WHERE id=old_parent;
        SELECT policy_id INTO new_policy FROM workflow_workflowcalendar WHERE id=new_parent;
    ELSIF TG_ARGV[0] = 'stage_timing_id' THEN
        SELECT policy_id INTO old_policy FROM workflow_workflowstagetiming WHERE id=old_parent;
        SELECT policy_id INTO new_policy FROM workflow_workflowstagetiming WHERE id=new_parent;
    ELSE
        old_policy := old_parent;
        new_policy := new_parent;
    END IF;
    -- Lock in the same order as publication. The lock serializes draft edits
    -- with the validation/publication transaction, including bulk ORM writes.
    FOR locked_id, parent_status IN
        SELECT id,status FROM workflow_workflowschedulepolicy
        WHERE id IN (old_policy,new_policy) ORDER BY id FOR UPDATE
    LOOP
        IF parent_status <> 'draft' THEN
            RAISE EXCEPTION 'Published scheduling configuration is immutable' USING ERRCODE = '23514';
        END IF;
    END LOOP;
    IF TG_OP = 'UPDATE' AND old_policy IS DISTINCT FROM new_policy THEN
        RAISE EXCEPTION 'Cannot move scheduling configuration across versions' USING ERRCODE = '23514';
    END IF;
    IF TG_OP <> 'DELETE' AND TG_TABLE_NAME = 'workflow_workflowstagetiming' THEN
        SELECT policy_id INTO calendar_policy FROM workflow_workflowcalendar
            WHERE id = (to_jsonb(NEW)->>'calendar_id')::bigint;
        IF calendar_policy IS DISTINCT FROM new_policy THEN
            RAISE EXCEPTION 'Stage calendar belongs to another policy' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION wf_sched_guard_forecast() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(OLD) - 'is_current') = (to_jsonb(NEW) - 'is_current')
           AND (OLD.is_current OR NOT NEW.is_current)
        THEN RETURN NEW; END IF;
    END IF;
    RAISE EXCEPTION 'Forecast history is append-only' USING ERRCODE = '23514';
END $$;

CREATE FUNCTION wf_sched_guard_detail() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE active_revision boolean;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT is_current INTO active_revision FROM workflow_workflowforecast
            WHERE id = NEW.forecast_id FOR UPDATE;
        IF active_revision AND
            current_setting('portal.scheduling_detail_revision', true) = NEW.forecast_id::text
        THEN RETURN NEW; END IF;
    END IF;
    RAISE EXCEPTION 'Forecast detail history is append-only' USING ERRCODE = '23514';
END $$;
"""


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        # The operational database is PostgreSQL. Other engines do not gain
        # this protection and must not be used for production scheduling.
        return
    schema_editor.execute(SQL)
    schema_editor.execute(f'CREATE TRIGGER wf_sched_guard BEFORE INSERT OR UPDATE OR DELETE ON {POLICY} FOR EACH ROW EXECUTE FUNCTION wf_sched_guard_policy()')
    for table, field in CONFIG.items():
        schema_editor.execute(f"CREATE TRIGGER wf_sched_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION wf_sched_guard_config('{field}')")
    schema_editor.execute(f'CREATE TRIGGER wf_sched_guard BEFORE UPDATE OR DELETE ON {FORECAST} FOR EACH ROW EXECUTE FUNCTION wf_sched_guard_forecast()')
    for table in DETAILS:
        schema_editor.execute(f'CREATE TRIGGER wf_sched_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION wf_sched_guard_detail()')


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in (POLICY, *CONFIG, FORECAST, *DETAILS):
        schema_editor.execute(f'DROP TRIGGER IF EXISTS wf_sched_guard ON {table}')
    for function in ('policy','config','forecast','detail'):
        schema_editor.execute(f'DROP FUNCTION IF EXISTS wf_sched_guard_{function}()')


class Migration(migrations.Migration):
    dependencies = [('workflow','0012_workflow_forecast_refresh')]
    operations = [migrations.RunPython(install,uninstall)]
