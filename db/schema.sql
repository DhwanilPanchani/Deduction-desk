DROP TABLE IF EXISTS disputes CASCADE;
DROP TABLE IF EXISTS ground_truth CASCADE;
DROP TABLE IF EXISTS deductions CASCADE;
DROP TABLE IF EXISTS remittances CASCADE;
DROP TABLE IF EXISTS trade_promotions CASCADE;
DROP TABLE IF EXISTS proof_of_delivery CASCADE;
DROP TABLE IF EXISTS invoices CASCADE;
DROP TABLE IF EXISTS purchase_orders CASCADE;
DROP TABLE IF EXISTS retailers CASCADE;
DROP TABLE IF EXISTS brands CASCADE;

CREATE TABLE brands (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE retailers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    retailer_code TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE purchase_orders (
    id BIGSERIAL PRIMARY KEY,
    po_number TEXT NOT NULL UNIQUE,
    brand_id BIGINT NOT NULL REFERENCES brands(id),
    retailer_id BIGINT NOT NULL REFERENCES retailers(id),
    product_sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    order_date DATE NOT NULL,
    expected_delivery_date DATE NOT NULL,
    ordered_qty INTEGER NOT NULL CHECK (ordered_qty > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_number TEXT NOT NULL UNIQUE,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(id),
    invoice_date DATE NOT NULL,
    invoiced_qty INTEGER NOT NULL CHECK (invoiced_qty > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    gross_amount NUMERIC(14, 2) NOT NULL CHECK (gross_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE proof_of_delivery (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL UNIQUE REFERENCES purchase_orders(id),
    delivery_date DATE NOT NULL,
    delivered_qty INTEGER NOT NULL CHECK (delivered_qty >= 0),
    damaged_qty INTEGER NOT NULL DEFAULT 0 CHECK (damaged_qty >= 0),
    signed_by TEXT NOT NULL,
    pod_reference TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE trade_promotions (
    id BIGSERIAL PRIMARY KEY,
    brand_id BIGINT NOT NULL REFERENCES brands(id),
    retailer_id BIGINT NOT NULL REFERENCES retailers(id),
    product_sku TEXT NOT NULL,
    promotion_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    discount_percent NUMERIC(5, 2) NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_date >= start_date)
);

CREATE TABLE remittances (
    id BIGSERIAL PRIMARY KEY,
    remittance_number TEXT NOT NULL UNIQUE,
    invoice_id BIGINT NOT NULL UNIQUE REFERENCES invoices(id),
    remittance_date DATE NOT NULL,
    invoice_amount NUMERIC(14, 2) NOT NULL CHECK (invoice_amount >= 0),
    paid_amount NUMERIC(14, 2) NOT NULL CHECK (paid_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE deductions (
    id BIGSERIAL PRIMARY KEY,
    deduction_number TEXT NOT NULL UNIQUE,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id),
    remittance_id BIGINT NOT NULL REFERENCES remittances(id),
    type TEXT NOT NULL CHECK (type IN ('shortage', 'pricing', 'promotional', 'compliance', 'damage')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'disputed', 'accepted')),
    claim_date DATE NOT NULL,
    claimed_qty INTEGER CHECK (claimed_qty IS NULL OR claimed_qty >= 0),
    claimed_unit_price NUMERIC(12, 2) CHECK (claimed_unit_price IS NULL OR claimed_unit_price >= 0),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    retailer_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE ground_truth (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL UNIQUE REFERENCES deductions(id) ON DELETE CASCADE,
    is_valid BOOLEAN NOT NULL,
    true_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE disputes (
    id BIGSERIAL PRIMARY KEY,
    deduction_id BIGINT NOT NULL UNIQUE REFERENCES deductions(id) ON DELETE CASCADE,
    opened_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    outcome TEXT,
    response_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_po_retailer ON purchase_orders(retailer_id);
CREATE INDEX idx_invoice_po ON invoices(purchase_order_id);
CREATE INDEX idx_promo_match ON trade_promotions(retailer_id, product_sku, start_date, end_date);
CREATE INDEX idx_deductions_invoice ON deductions(invoice_id);
CREATE INDEX idx_deductions_type_status ON deductions(type, status);
