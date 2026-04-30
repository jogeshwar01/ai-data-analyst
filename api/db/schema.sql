CREATE TABLE IF NOT EXISTS territory_dim (
    territory_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    geo_type TEXT,
    parent_territory_id INTEGER
);

CREATE TABLE IF NOT EXISTS rep_dim (
    rep_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    region TEXT
);

CREATE TABLE IF NOT EXISTS account_dim (
    account_id INTEGER PRIMARY KEY,
    name TEXT,
    account_type TEXT,
    address TEXT,
    territory_id INTEGER REFERENCES territory_dim(territory_id)
);

CREATE TABLE IF NOT EXISTS hcp_dim (
    hcp_id BIGINT PRIMARY KEY,
    full_name TEXT,
    specialty TEXT,
    tier TEXT,
    territory_id INTEGER REFERENCES territory_dim(territory_id)
);

CREATE TABLE IF NOT EXISTS date_dim (
    date_id INTEGER PRIMARY KEY,
    calendar_date DATE,
    year INTEGER,
    quarter TEXT,
    week_num INTEGER,
    day_of_week TEXT
);

CREATE TABLE IF NOT EXISTS fact_rx (
    hcp_id BIGINT REFERENCES hcp_dim(hcp_id),
    date_id INTEGER REFERENCES date_dim(date_id),
    brand_code TEXT,
    trx_cnt INTEGER,
    nrx_cnt INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fact_rx_hcp ON fact_rx(hcp_id);
CREATE INDEX IF NOT EXISTS idx_fact_rx_date ON fact_rx(date_id);

CREATE TABLE IF NOT EXISTS fact_rep_activity (
    activity_id INTEGER PRIMARY KEY,
    rep_id INTEGER REFERENCES rep_dim(rep_id),
    hcp_id BIGINT REFERENCES hcp_dim(hcp_id),
    account_id INTEGER REFERENCES account_dim(account_id),
    date_id INTEGER REFERENCES date_dim(date_id),
    activity_type TEXT,
    status TEXT,
    time_of_day TEXT,
    duration_min INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fact_rep_activity_rep ON fact_rep_activity(rep_id);
CREATE INDEX IF NOT EXISTS idx_fact_rep_activity_hcp ON fact_rep_activity(hcp_id);
CREATE INDEX IF NOT EXISTS idx_fact_rep_activity_date ON fact_rep_activity(date_id);

CREATE TABLE IF NOT EXISTS fact_payor_mix (
    account_id INTEGER REFERENCES account_dim(account_id),
    date_id INTEGER REFERENCES date_dim(date_id),
    payor_type TEXT,
    pct_of_volume NUMERIC(5,2)
);
CREATE INDEX IF NOT EXISTS idx_fact_payor_mix_account ON fact_payor_mix(account_id);

CREATE TABLE IF NOT EXISTS fact_ln_metrics (
    entity_type TEXT,
    entity_id BIGINT,
    quarter_id TEXT,
    ln_patient_cnt INTEGER,
    est_market_share NUMERIC(6,2)
);
CREATE INDEX IF NOT EXISTS idx_fact_ln_metrics_entity ON fact_ln_metrics(entity_type, entity_id);

-- Convenience view: enriched Rx with HCP + territory context
CREATE OR REPLACE VIEW v_rx_enriched AS
SELECT
    r.hcp_id,
    h.full_name AS hcp_name,
    h.specialty,
    h.tier,
    h.territory_id,
    t.name AS territory_name,
    r.date_id,
    d.calendar_date,
    d.year,
    d.quarter,
    r.brand_code,
    r.trx_cnt,
    r.nrx_cnt
FROM fact_rx r
JOIN hcp_dim h USING (hcp_id)
JOIN date_dim d USING (date_id)
JOIN territory_dim t ON h.territory_id = t.territory_id;

-- Convenience view: rep activity enriched with rep + HCP + date
CREATE OR REPLACE VIEW v_activity_enriched AS
SELECT
    a.activity_id,
    a.rep_id,
    rp.first_name || ' ' || rp.last_name AS rep_name,
    rp.region,
    a.hcp_id,
    h.full_name AS hcp_name,
    h.specialty,
    h.tier,
    h.territory_id,
    a.account_id,
    a.date_id,
    d.calendar_date,
    a.activity_type,
    a.status,
    a.duration_min
FROM fact_rep_activity a
JOIN rep_dim rp USING (rep_id)
JOIN hcp_dim h USING (hcp_id)
JOIN date_dim d USING (date_id);
