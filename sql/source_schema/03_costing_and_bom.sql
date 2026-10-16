BEGIN;

CREATE TABLE IF NOT EXISTS raw.exchange_rates (
    rate_date DATE NOT NULL,
    currency_code CHAR(3) NOT NULL,
    rate_to_brl NUMERIC(14, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT pk_exchange_rates
        PRIMARY KEY (rate_date, currency_code),
    CONSTRAINT chk_exchange_rates_currency
        CHECK (currency_code IN ('BRL', 'USD', 'EUR')),
    CONSTRAINT chk_exchange_rates_value
        CHECK (rate_to_brl > 0),
    CONSTRAINT chk_exchange_rates_brl
        CHECK (
            currency_code <> 'BRL'
            OR rate_to_brl = 1
        )
);

CREATE TABLE IF NOT EXISTS raw.component_standard_cost_history (
    standard_cost_id BIGINT PRIMARY KEY,
    component_id INTEGER NOT NULL,
    plant_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    standard_unit_cost_brl NUMERIC(18, 6) NOT NULL,
    revision_reason VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_component_standard_cost_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT fk_component_standard_cost_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT uq_component_standard_cost_period
        UNIQUE (component_id, plant_id, valid_from),
    CONSTRAINT chk_component_standard_cost_value
        CHECK (standard_unit_cost_brl > 0),
    CONSTRAINT chk_component_standard_cost_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_component_standard_cost_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.component_cost_history (
    component_cost_id BIGINT PRIMARY KEY,
    component_id INTEGER NOT NULL,
    plant_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    moving_average_unit_cost_brl NUMERIC(18, 6) NOT NULL,
    cost_source VARCHAR(30) NOT NULL,
    source_reference VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_component_cost_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT fk_component_cost_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT uq_component_cost_period
        UNIQUE (component_id, plant_id, valid_from),
    CONSTRAINT chk_component_cost_value
        CHECK (moving_average_unit_cost_brl > 0),
    CONSTRAINT chk_component_cost_source
        CHECK (
            cost_source IN (
                'OPENING_BALANCE',
                'PURCHASE_RECEIPT',
                'INVENTORY_ADJUSTMENT'
            )
        ),
    CONSTRAINT chk_component_cost_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_component_cost_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.bill_of_materials (
    bom_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    bom_version VARCHAR(20) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    bom_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_bill_of_materials_product
        FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT uq_bill_of_materials_version
        UNIQUE (product_id, bom_version),
    CONSTRAINT chk_bill_of_materials_status
        CHECK (bom_status IN ('ACTIVE', 'OBSOLETE')),
    CONSTRAINT chk_bill_of_materials_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_bill_of_materials_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.bill_of_material_items (
    bom_item_id BIGINT PRIMARY KEY,
    bom_id INTEGER NOT NULL,
    component_id INTEGER NOT NULL,
    item_sequence SMALLINT NOT NULL,
    base_quantity_per_unit NUMERIC(18, 6) NOT NULL,
    standard_scrap_rate NUMERIC(9, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_bill_of_material_items_bom
        FOREIGN KEY (bom_id)
        REFERENCES raw.bill_of_materials (bom_id),
    CONSTRAINT fk_bill_of_material_items_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT uq_bill_of_material_items_component
        UNIQUE (bom_id, component_id),
    CONSTRAINT uq_bill_of_material_items_sequence
        UNIQUE (bom_id, item_sequence),
    CONSTRAINT chk_bill_of_material_items_quantity
        CHECK (base_quantity_per_unit > 0),
    CONSTRAINT chk_bill_of_material_items_scrap
        CHECK (
            standard_scrap_rate >= 0
            AND standard_scrap_rate < 1
        ),
    CONSTRAINT chk_bill_of_material_items_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.standard_conversion_costs (
    standard_conversion_cost_id BIGINT PRIMARY KEY,
    product_id INTEGER NOT NULL,
    plant_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    standard_labor_hours_per_unit NUMERIC(12, 6) NOT NULL,
    standard_machine_hours_per_unit NUMERIC(12, 6) NOT NULL,
    labor_rate_per_hour_brl NUMERIC(14, 4) NOT NULL,
    machine_rate_per_hour_brl NUMERIC(14, 4) NOT NULL,
    overhead_cost_per_unit_brl NUMERIC(14, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_standard_conversion_cost_product
        FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT fk_standard_conversion_cost_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT uq_standard_conversion_cost_period
        UNIQUE (product_id, plant_id, valid_from),
    CONSTRAINT chk_standard_conversion_cost_values
        CHECK (
            standard_labor_hours_per_unit >= 0
            AND standard_machine_hours_per_unit >= 0
            AND labor_rate_per_hour_brl >= 0
            AND machine_rate_per_hour_brl >= 0
            AND overhead_cost_per_unit_brl >= 0
        ),
    CONSTRAINT chk_standard_conversion_cost_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_standard_conversion_cost_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;