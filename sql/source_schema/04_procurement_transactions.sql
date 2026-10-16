BEGIN;

CREATE TABLE IF NOT EXISTS raw.purchase_orders (
    purchase_order_id BIGINT PRIMARY KEY,
    purchase_order_number VARCHAR(30) NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL,
    plant_id SMALLINT NOT NULL,
    order_date DATE NOT NULL,
    expected_delivery_date DATE NOT NULL,
    currency_code CHAR(3) NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_purchase_orders_supplier
        FOREIGN KEY (supplier_id)
        REFERENCES raw.suppliers (supplier_id),
    CONSTRAINT fk_purchase_orders_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT chk_purchase_orders_delivery_date
        CHECK (expected_delivery_date >= order_date),
    CONSTRAINT chk_purchase_orders_currency
        CHECK (currency_code IN ('BRL', 'USD', 'EUR')),
    CONSTRAINT chk_purchase_orders_status
        CHECK (
            order_status IN (
                'OPEN',
                'PARTIALLY_RECEIVED',
                'RECEIVED',
                'CANCELLED'
            )
        ),
    CONSTRAINT chk_purchase_orders_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.purchase_order_items (
    purchase_order_item_id BIGINT PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL,
    line_number SMALLINT NOT NULL,
    component_id INTEGER NOT NULL,
    ordered_quantity NUMERIC(18, 6) NOT NULL,
    unit_price_original_currency NUMERIC(18, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_purchase_order_items_order
        FOREIGN KEY (purchase_order_id)
        REFERENCES raw.purchase_orders (purchase_order_id),
    CONSTRAINT fk_purchase_order_items_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT uq_purchase_order_items_line
        UNIQUE (purchase_order_id, line_number),
    CONSTRAINT chk_purchase_order_items_quantity
        CHECK (ordered_quantity > 0),
    CONSTRAINT chk_purchase_order_items_price
        CHECK (unit_price_original_currency > 0),
    CONSTRAINT chk_purchase_order_items_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.component_receipts (
    receipt_item_id BIGINT PRIMARY KEY,
    purchase_order_item_id BIGINT NOT NULL,
    receipt_number VARCHAR(30) NOT NULL,
    receipt_line_number SMALLINT NOT NULL,
    receipt_date DATE NOT NULL,
    received_quantity NUMERIC(18, 6) NOT NULL,
    exchange_rate_to_brl NUMERIC(14, 6) NOT NULL,
    international_freight_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    insurance_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    nonrecoverable_import_tax_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    domestic_freight_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    other_landed_cost_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_component_receipts_order_item
        FOREIGN KEY (purchase_order_item_id)
        REFERENCES raw.purchase_order_items (purchase_order_item_id),
    CONSTRAINT uq_component_receipts_line
        UNIQUE (receipt_number, receipt_line_number),
    CONSTRAINT chk_component_receipts_quantity
        CHECK (received_quantity > 0),
    CONSTRAINT chk_component_receipts_exchange_rate
        CHECK (exchange_rate_to_brl > 0),
    CONSTRAINT chk_component_receipts_landed_costs
        CHECK (
            international_freight_brl >= 0
            AND insurance_brl >= 0
            AND nonrecoverable_import_tax_brl >= 0
            AND domestic_freight_brl >= 0
            AND other_landed_cost_brl >= 0
        ),
    CONSTRAINT chk_component_receipts_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;