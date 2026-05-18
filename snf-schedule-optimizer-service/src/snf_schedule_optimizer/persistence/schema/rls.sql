-- Row-Level Security for multi-tenant isolation
-- Apply to core tables. Run this in the target database.

ALTER TABLE shift ENABLE ROW LEVEL SECURITY;
ALTER TABLE shift FORCE ROW LEVEL SECURITY;

ALTER TABLE schedule_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_record FORCE ROW LEVEL SECURITY;

ALTER TABLE optimization_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_run FORCE ROW LEVEL SECURITY;

ALTER TABLE employee ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee FORCE ROW LEVEL SECURITY;

ALTER TABLE time_punch ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_punch FORCE ROW LEVEL SECURITY;

-- Example RLS policies (must be executed per-session after setting app.current_org_id):
-- CREATE POLICY tenant_isolation ON shift
--     FOR ALL
--     USING (org_id = current_setting('app.current_org_id')::int)
--     WITH CHECK (org_id = current_setting('app.current_org_id')::int);
