BEGIN;

CREATE TABLE IF NOT EXISTS raw.plants (
    plant_id SMALLINT PRIMARY KEY,
    plant_code VARCHAR(20) NOT NULL UNIQUE,
    plant_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state_code CHAR(2) NOT NULL,
    country_code CHAR(2) NOT NULL DEFAULT 'BR',
    active_from DATE NOT NULL,
    active_to DATE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_plants_active_dates
        CHECK (active_to IS NULL OR active_to >= active_from),
    CONSTRAINT chk_plants_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.production_lines (
    production_line_id SMALLINT PRIMARY KEY,
    plant_id SMALLINT NOT NULL,
    line_code VARCHAR(20) NOT NULL UNIQUE,
    line_name VARCHAR(100) NOT NULL,
    active_from DATE NOT NULL,
    active_to DATE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_production_lines_plant
        FOREIGN KEY (plant_id) REFERENCES raw.plants (plant_id),
    CONSTRAINT chk_production_lines_active_dates
        CHECK (active_to IS NULL OR active_to >= active_from),
    CONSTRAINT chk_production_lines_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.product_families (
    product_family_id SMALLINT PRIMARY KEY,
    family_code VARCHAR(20) NOT NULL UNIQUE,
    family_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_product_families_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id INTEGER PRIMARY KEY,
    product_family_id SMALLINT NOT NULL,
    product_code VARCHAR(30) NOT NULL UNIQUE,
    product_name VARCHAR(150) NOT NULL,
    unit_of_measure VARCHAR(10) NOT NULL DEFAULT 'EA',
    net_weight_kg NUMERIC(12, 4) NOT NULL,
    gross_weight_kg NUMERIC(12, 4) NOT NULL,
    package_volume_m3 NUMERIC(12, 6) NOT NULL,
    launch_date DATE NOT NULL,
    discontinue_date DATE,
    product_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_products_family
        FOREIGN KEY (product_family_id)
        REFERENCES raw.product_families (product_family_id),
    CONSTRAINT chk_products_weights
        CHECK (
            net_weight_kg > 0
            AND gross_weight_kg >= net_weight_kg
            AND package_volume_m3 > 0
        ),
    CONSTRAINT chk_products_status
        CHECK (product_status IN ('ACTIVE', 'DISCONTINUED')),
    CONSTRAINT chk_products_dates
        CHECK (
            discontinue_date IS NULL
            OR discontinue_date >= launch_date
        ),
    CONSTRAINT chk_products_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.component_categories (
    component_category_id SMALLINT PRIMARY KEY,
    category_code VARCHAR(20) NOT NULL UNIQUE,
    category_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_component_categories_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.components (
    component_id INTEGER PRIMARY KEY,
    component_category_id SMALLINT NOT NULL,
    component_code VARCHAR(30) NOT NULL UNIQUE,
    component_name VARCHAR(150) NOT NULL,
    unit_of_measure VARCHAR(10) NOT NULL,
    sourcing_type VARCHAR(20) NOT NULL,
    preferred_currency CHAR(3) NOT NULL,
    standard_lead_time_days SMALLINT NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_components_category
        FOREIGN KEY (component_category_id)
        REFERENCES raw.component_categories (component_category_id),
    CONSTRAINT chk_components_sourcing
        CHECK (sourcing_type IN ('DOMESTIC', 'IMPORTED')),
    CONSTRAINT chk_components_currency
        CHECK (preferred_currency IN ('BRL', 'USD', 'EUR')),
    CONSTRAINT chk_components_lead_time
        CHECK (standard_lead_time_days >= 0),
    CONSTRAINT chk_components_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.suppliers (
    supplier_id INTEGER PRIMARY KEY,
    supplier_code VARCHAR(20) NOT NULL UNIQUE,
    supplier_name VARCHAR(150) NOT NULL,
    country_code CHAR(2) NOT NULL,
    state_code CHAR(2),
    default_currency CHAR(3) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_suppliers_currency
        CHECK (default_currency IN ('BRL', 'USD', 'EUR')),
    CONSTRAINT chk_suppliers_domestic_state
        CHECK (
            country_code <> 'BR'
            OR state_code IS NOT NULL
        ),
    CONSTRAINT chk_suppliers_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;