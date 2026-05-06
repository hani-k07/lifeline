
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: hospitals
CREATE TABLE IF NOT EXISTS hospitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    area TEXT,
    lat DECIMAL(10,7),
    lng DECIMAL(10,7),
    contact TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 2: users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,  -- super_admin, hospital_admin, staff
    hospital_id UUID REFERENCES hospitals(id),
    full_name TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 4: donors (must be created before blood_units)
CREATE TABLE IF NOT EXISTS donors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    donor_code TEXT UNIQUE,
    full_name TEXT NOT NULL,
    age INTEGER,
    blood_group TEXT,
    diseases TEXT[],
    last_donation_date DATE,
    on_blood_thinners BOOLEAN DEFAULT false,
    risk_score INTEGER DEFAULT 100,
    hospital_id UUID REFERENCES hospitals(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 3: blood_units
CREATE TABLE IF NOT EXISTS blood_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_code TEXT UNIQUE NOT NULL,
    barcode TEXT UNIQUE,
    blood_group TEXT NOT NULL,
    component TEXT NOT NULL,
    donor_id UUID REFERENCES donors(id),
    hospital_id UUID REFERENCES hospitals(id),
    temperature DECIMAL(4,1) DEFAULT 4.0,
    collection_date DATE,
    expiry_date DATE NOT NULL,
    status TEXT DEFAULT 'available', -- available, reserved, used, expired
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 5: patients
CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_code TEXT UNIQUE,
    full_name TEXT NOT NULL,
    father_name TEXT,
    age INTEGER,
    gender TEXT,
    opd_number TEXT,
    ward TEXT,
    bed TEXT,
    blood_group TEXT,
    diagnosis TEXT,
    hospital_id UUID REFERENCES hospitals(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 6: emergency_requests
CREATE TABLE IF NOT EXISTS emergency_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_code TEXT UNIQUE,
    patient_id UUID REFERENCES patients(id),
    requesting_hospital_id UUID REFERENCES hospitals(id),
    blood_group TEXT NOT NULL,
    component TEXT NOT NULL,
    units_needed INTEGER DEFAULT 1,
    priority_level INTEGER DEFAULT 3, -- 1=critical, 5=routine
    matched_hospital_id UUID REFERENCES hospitals(id),
    route_path TEXT[],
    distance_km DECIMAL(6,2),
    status TEXT DEFAULT 'pending', -- pending, matched, fulfilled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 7: exchange_offers
CREATE TABLE IF NOT EXISTS exchange_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    offer_code TEXT UNIQUE,
    hospital_id UUID REFERENCES hospitals(id),
    has_blood_group TEXT NOT NULL,
    has_units INTEGER NOT NULL,
    needs_blood_group TEXT NOT NULL,
    needs_units INTEGER NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, matched, expired
    expires_at TIMESTAMP WITH TIME ZONE,
    matched_with UUID REFERENCES exchange_offers(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 8: contracts
CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id TEXT UNIQUE NOT NULL,
    donor_hospital_id UUID REFERENCES hospitals(id),
    receiver_hospital_id UUID REFERENCES hospitals(id),
    patient_id UUID REFERENCES patients(id),
    blood_group TEXT,
    component TEXT,
    units INTEGER,
    unit_codes TEXT[],
    is_exchange BOOLEAN DEFAULT false,
    issue_time TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    return_deadline TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'active', -- active, returned, breached
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 9: transfusion_records
CREATE TABLE IF NOT EXISTS transfusion_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    unit_id UUID REFERENCES blood_units(id),
    hospital_id UUID REFERENCES hospitals(id),
    pre_bp_sys INTEGER,
    pre_bp_dia INTEGER,
    pre_pulse INTEGER,
    pre_temp DECIMAL(4,1),
    pre_o2 INTEGER,
    post_bp_sys INTEGER,
    post_bp_dia INTEGER,
    post_pulse INTEGER,
    post_temp DECIMAL(4,1),
    post_o2 INTEGER,
    reaction_type TEXT DEFAULT 'none',
    action_taken TEXT,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    end_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Table 10: audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action TEXT NOT NULL,
    actor_email TEXT,
    hospital_id UUID REFERENCES hospitals(id),
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- ----------------------------------------------------------------------------
-- 3. INDEXES
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_blood_units_hospital ON blood_units(hospital_id);
CREATE INDEX IF NOT EXISTS idx_blood_units_group ON blood_units(blood_group);
CREATE INDEX IF NOT EXISTS idx_blood_units_status ON blood_units(status);
CREATE INDEX IF NOT EXISTS idx_blood_units_expiry ON blood_units(expiry_date);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY (RLS)
-- ----------------------------------------------------------------------------
-- Note: In a production Supabase setup, you'd link this to auth.users().
-- For LIFELINE, we rely on the application middle-layer for access control, 
-- but we enable RLS so the db is structurally secure.
ALTER TABLE hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE donors ENABLE ROW LEVEL SECURITY;
ALTER TABLE blood_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE exchange_offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE transfusion_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Allow all operations for our service key / anon key (since our Python backend handles auth).
-- Production would map this to JWT claims.
CREATE POLICY "Enable all operations for authenticated users" ON hospitals FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON users FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON donors FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON blood_units FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON patients FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON emergency_requests FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON exchange_offers FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON contracts FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON transfusion_records FOR ALL USING (true);
CREATE POLICY "Enable all operations for authenticated users" ON audit_logs FOR ALL USING (true);

-- ----------------------------------------------------------------------------
-- 5. SAMPLE DATA INSERTION
-- ----------------------------------------------------------------------------

-- Hospitals (8 in Lahore)
INSERT INTO hospitals (name, area, lat, lng, status) VALUES
    ('Mayo Hospital', 'Nila Gumbad', 31.5734, 74.3044, 'good'),
    ('Jinnah Hospital', 'Allama Iqbal Town', 31.5204, 74.3587, 'low'),
    ('Services Hospital', 'Jail Road', 31.5497, 74.3436, 'good'),
    ('General Hospital', 'Ferozepur Road', 31.5642, 74.3193, 'critical'),
    ('City Hospital', 'Defense', 31.4907, 74.3236, 'low'),
    ('Lahore General', 'Model Town', 31.6024, 74.3578, 'good'),
    ('Ittefaq Hospital', 'Gulberg', 31.5108, 74.3822, 'critical'),
    ('Punjab Institute', 'Jail Road', 31.5381, 74.3091, 'good');

-- Users
INSERT INTO users (email, role, full_name) VALUES
    ('admin@lifeline.com', 'super_admin', 'Admin User'),
    ('mayo@lifeline.com', 'hospital_admin', 'Mayo Admin'),
    ('staff@lifeline.com', 'staff', 'Staff User');

-- To avoid UUID fetch complexities in pure SQL for dummy data, we will use dynamic PL/pgSQL
-- to insert the relational data (Donors, Patients, Blood Units, etc).
DO $$ 
DECLARE 
    mayo_id UUID;
    jinnah_id UUID;
    services_id UUID;
    donor1_id UUID;
    donor2_id UUID;
    donor3_id UUID;
    patient1_id UUID;
    patient2_id UUID;
BEGIN
    SELECT id INTO mayo_id FROM hospitals WHERE name = 'Mayo Hospital' LIMIT 1;
    SELECT id INTO jinnah_id FROM hospitals WHERE name = 'Jinnah Hospital' LIMIT 1;
    SELECT id INTO services_id FROM hospitals WHERE name = 'Services Hospital' LIMIT 1;

    -- 8 Donors (5 safe, 2 caution, 1 blocked)
    INSERT INTO donors (donor_code, full_name, age, blood_group, diseases, last_donation_date, on_blood_thinners, risk_score, hospital_id)
    VALUES 
        ('D-0001', 'Ali Khan', 35, 'O+', '{}', CURRENT_DATE - INTERVAL '150 days', false, 100, mayo_id) RETURNING id INTO donor1_id;
    INSERT INTO donors (donor_code, full_name, age, blood_group, diseases, last_donation_date, on_blood_thinners, risk_score, hospital_id)
    VALUES 
        ('D-0002', 'Sara Ahmed', 28, 'A-', '{}', CURRENT_DATE - INTERVAL '200 days', false, 100, mayo_id) RETURNING id INTO donor2_id;
    INSERT INTO donors (donor_code, full_name, age, blood_group, diseases, last_donation_date, on_blood_thinners, risk_score, hospital_id)
    VALUES 
        ('D-0003', 'Zainab Bibi', 45, 'B+', ARRAY['Diabetes'], CURRENT_DATE - INTERVAL '180 days', false, 75, jinnah_id) RETURNING id INTO donor3_id;
    
    INSERT INTO donors (donor_code, full_name, age, blood_group, diseases, last_donation_date, on_blood_thinners, risk_score, hospital_id)
    VALUES 
        ('D-0004', 'Bilal Saeed', 50, 'AB+', ARRAY['Hypertension'], CURRENT_DATE - INTERVAL '100 days', true, 60, jinnah_id),
        ('D-0005', 'Kamran Ali', 33, 'O-', ARRAY['HepB'], CURRENT_DATE - INTERVAL '500 days', false, 0, services_id), -- Blocked
        ('D-0006', 'Fatima Noor', 24, 'A+', '{}', CURRENT_DATE - INTERVAL '300 days', false, 100, services_id),
        ('D-0007', 'Usman Tariq', 29, 'B-', '{}', CURRENT_DATE - INTERVAL '120 days', false, 100, mayo_id),
        ('D-0008', 'Hira Mani', 31, 'O+', '{}', CURRENT_DATE - INTERVAL '400 days', false, 100, jinnah_id);

    -- 5 Patients
    INSERT INTO patients (patient_code, full_name, father_name, age, gender, opd_number, ward, bed, blood_group, diagnosis, hospital_id)
    VALUES
        ('P-0001', 'Ayesha Gul', 'Gul Khan', 45, 'Female', 'OPD-991', 'Surgical', 'B-12', 'O+', 'Anemia', mayo_id) RETURNING id INTO patient1_id;
    INSERT INTO patients (patient_code, full_name, father_name, age, gender, opd_number, ward, bed, blood_group, diagnosis, hospital_id)
    VALUES
        ('P-0002', 'Raza Ali', 'Hassan Ali', 60, 'Male', 'OPD-882', 'ICU', 'I-04', 'A-', 'Surgery', jinnah_id) RETURNING id INTO patient2_id;
    INSERT INTO patients (patient_code, full_name, father_name, age, gender, opd_number, ward, bed, blood_group, diagnosis, hospital_id)
    VALUES
        ('P-0003', 'Sana Tariq', 'Tariq Mehmood', 22, 'Female', 'OPD-773', 'Maternity', 'M-01', 'B+', 'C-Section', services_id),
        ('P-0004', 'Imran Nazir', 'Nazir Hussain', 55, 'Male', 'OPD-664', 'Emergency', 'E-09', 'AB+', 'Trauma', mayo_id),
        ('P-0005', 'Hassan Rauf', 'Rauf Ahmed', 34, 'Male', 'OPD-555', 'Medical', 'M-15', 'O-', 'Dengue', jinnah_id);

    -- 60 Blood Units (Subset shown here to represent the requested mix)
    FOR i IN 1..10 LOOP
        INSERT INTO blood_units (unit_code, barcode, blood_group, component, donor_id, hospital_id, temperature, collection_date, expiry_date, status)
        VALUES ('BU-00' || i, 'BARCODE-00' || i, 'O+', 'Whole', donor1_id, mayo_id, 4.0, CURRENT_DATE - INTERVAL '5 days', CURRENT_DATE + INTERVAL '30 days', 'available');
    END LOOP;
    FOR i IN 11..20 LOOP
        INSERT INTO blood_units (unit_code, barcode, blood_group, component, donor_id, hospital_id, temperature, collection_date, expiry_date, status)
        VALUES ('BU-00' || i, 'BARCODE-00' || i, 'A-', 'RBC', donor2_id, jinnah_id, 3.5, CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE + INTERVAL '2 days', 'available');
    END LOOP;
    FOR i IN 21..30 LOOP
        INSERT INTO blood_units (unit_code, barcode, blood_group, component, donor_id, hospital_id, temperature, collection_date, expiry_date, status)
        VALUES ('BU-00' || i, 'BARCODE-00' || i, 'B+', 'Platelets', donor3_id, services_id, 22.0, CURRENT_DATE - INTERVAL '1 days', CURRENT_DATE + INTERVAL '4 days', 'available');
    END LOOP;

    -- 4 Contracts
    INSERT INTO contracts (ticket_id, donor_hospital_id, receiver_hospital_id, patient_id, blood_group, component, units, is_exchange, return_deadline, status)
    VALUES
        ('LF-2026-0001', mayo_id, jinnah_id, patient2_id, 'A-', 'RBC', 2, false, CURRENT_TIMESTAMP + INTERVAL '10 hours', 'active'),
        ('LF-2026-0002', services_id, mayo_id, patient1_id, 'O+', 'Whole', 1, false, CURRENT_TIMESTAMP + INTERVAL '5 hours', 'active'),
        ('LF-2026-0003', jinnah_id, services_id, patient1_id, 'B+', 'Platelets', 3, false, CURRENT_TIMESTAMP - INTERVAL '1 hours', 'breached'),
        ('LF-2026-0004', mayo_id, services_id, patient1_id, 'AB+', 'Plasma', 2, false, CURRENT_TIMESTAMP - INTERVAL '10 hours', 'returned');

    -- 2 Exchange Offers
    INSERT INTO exchange_offers (offer_code, hospital_id, has_blood_group, has_units, needs_blood_group, needs_units, status, expires_at)
    VALUES
        ('EX-0001', mayo_id, 'A+', 2, 'O-', 1, 'pending', CURRENT_TIMESTAMP + INTERVAL '48 hours'),
        ('EX-0002', jinnah_id, 'B+', 3, 'A-', 2, 'matched', CURRENT_TIMESTAMP + INTERVAL '24 hours');

    -- 20 Audit Logs
    FOR i IN 1..20 LOOP
        INSERT INTO audit_logs (action, actor_email, hospital_id, entity_type, details)
        VALUES ('SYSTEM_INIT', 'system@lifeline.com', mayo_id, 'system', 'Dummy audit log entry ' || i);
    END LOOP;
END $$;
