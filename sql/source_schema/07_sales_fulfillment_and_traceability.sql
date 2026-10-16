BEGIN;

CREATE TABLE IF NOT EXISTS raw.shipments (
    shipment_id BIGINT PRIMARY KEY,
    shipment_number VARCHAR(30) NOT NULL UNIQUE,
    sales_order_id BIGINT NOT NULL,
    plant_id SMALLINT NOT NULL,
    carrier_name VARCHAR(150) NOT NULL,
    shipment_date DATE NOT NULL,
    delivery_date DATE,
    shipment_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_shipments_sales_order
        FOREIGN KEY (sales_order_id)
        REFERENCES raw.sales_orders (sales_order_id),
    CONSTRAINT fk_shipments_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT chk_shipments_delivery_date
        CHECK (
            delivery_date IS NULL
            OR delivery_date >= shipment_date
        ),
    CONSTRAINT chk_shipments_status
        CHECK (
            shipment_status IN (
                'PLANNED',
                'SHIPPED',
                'DELIVERED',
                'CANCELLED'
            )
        ),
    CONSTRAINT chk_shipments_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.shipment_items (
    shipment_item_id BIGINT PRIMARY KEY,
    shipment_id BIGINT NOT NULL,
    sales_order_item_id BIGINT NOT NULL,
    shipped_quantity NUMERIC(18, 6) NOT NULL,
    gross_weight_kg NUMERIC(18, 6),
    volume_m3 NUMERIC(18, 8),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_shipment_items_shipment
        FOREIGN KEY (shipment_id)
        REFERENCES raw.shipments (shipment_id),
    CONSTRAINT fk_shipment_items_sales_item
        FOREIGN KEY (sales_order_item_id)
        REFERENCES raw.sales_order_items (sales_order_item_id),
    CONSTRAINT uq_shipment_items_sales_item
        UNIQUE (shipment_id, sales_order_item_id),
    CONSTRAINT chk_shipment_items_quantity
        CHECK (shipped_quantity > 0),
    CONSTRAINT chk_shipment_items_weight
        CHECK (gross_weight_kg IS NULL OR gross_weight_kg > 0),
    CONSTRAINT chk_shipment_items_volume
        CHECK (volume_m3 IS NULL OR volume_m3 > 0),
    CONSTRAINT chk_shipment_items_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.shipment_freight_costs (
    freight_cost_id BIGINT PRIMARY KEY,
    shipment_id BIGINT NOT NULL UNIQUE,
    freight_date DATE NOT NULL,
    freight_responsibility VARCHAR(20) NOT NULL,
    base_freight_brl NUMERIC(18, 4) NOT NULL,
    fuel_surcharge_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    insurance_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    other_charge_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_shipment_freight_costs_shipment
        FOREIGN KEY (shipment_id)
        REFERENCES raw.shipments (shipment_id),
    CONSTRAINT chk_shipment_freight_responsibility
        CHECK (
            freight_responsibility IN (
                'COMPANY',
                'CUSTOMER'
            )
        ),
    CONSTRAINT chk_shipment_freight_cost_values
        CHECK (
            base_freight_brl >= 0
            AND fuel_surcharge_brl >= 0
            AND insurance_brl >= 0
            AND other_charge_brl >= 0
        ),
    CONSTRAINT chk_shipment_freight_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_commissions (
    commission_id BIGINT PRIMARY KEY,
    sales_order_id BIGINT NOT NULL,
    sales_order_item_id BIGINT,
    salesperson_id SMALLINT NOT NULL,
    commission_date DATE NOT NULL,
    commission_scope VARCHAR(20) NOT NULL,
    commission_rate NUMERIC(9, 6),
    commission_amount_brl NUMERIC(18, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_commissions_order
        FOREIGN KEY (sales_order_id)
        REFERENCES raw.sales_orders (sales_order_id),
    CONSTRAINT fk_sales_commissions_item
        FOREIGN KEY (sales_order_item_id)
        REFERENCES raw.sales_order_items (sales_order_item_id),
    CONSTRAINT fk_sales_commissions_salesperson
        FOREIGN KEY (salesperson_id)
        REFERENCES raw.salespeople (salesperson_id),
    CONSTRAINT chk_sales_commissions_scope
        CHECK (
            (
                commission_scope = 'ORDER'
                AND sales_order_item_id IS NULL
            )
            OR (
                commission_scope = 'ITEM'
                AND sales_order_item_id IS NOT NULL
            )
        ),
    CONSTRAINT chk_sales_commissions_rate
        CHECK (
            commission_rate IS NULL
            OR (
                commission_rate >= 0
                AND commission_rate < 1
            )
        ),
    CONSTRAINT chk_sales_commissions_amount
        CHECK (commission_amount_brl >= 0),
    CONSTRAINT chk_sales_commissions_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_variable_expenses (
    variable_expense_id BIGINT PRIMARY KEY,
    sales_order_item_id BIGINT NOT NULL,
    expense_date DATE NOT NULL,
    expense_type VARCHAR(40) NOT NULL,
    expense_amount_brl NUMERIC(18, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_variable_expenses_item
        FOREIGN KEY (sales_order_item_id)
        REFERENCES raw.sales_order_items (sales_order_item_id),
    CONSTRAINT chk_sales_variable_expenses_type
        CHECK (
            expense_type IN (
                'PAYMENT_FEE',
                'PACKAGING',
                'WARRANTY_PROVISION',
                'OTHER'
            )
        ),
    CONSTRAINT chk_sales_variable_expenses_amount
        CHECK (expense_amount_brl >= 0),
    CONSTRAINT chk_sales_variable_expenses_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_returns (
    return_item_id BIGINT PRIMARY KEY,
    return_number VARCHAR(30) NOT NULL,
    return_line_number SMALLINT NOT NULL,
    original_sales_order_item_id BIGINT NOT NULL,
    return_date DATE NOT NULL,
    returned_quantity NUMERIC(18, 6) NOT NULL,
    restocked_quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    rework_quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    scrapped_quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    unknown_disposition_quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    refund_unit_amount_brl NUMERIC(18, 4) NOT NULL,
    return_freight_cost_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    return_processing_cost_brl NUMERIC(18, 4) NOT NULL DEFAULT 0,
    return_reason_code VARCHAR(30) NOT NULL,
    return_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_returns_original_item
        FOREIGN KEY (original_sales_order_item_id)
        REFERENCES raw.sales_order_items (sales_order_item_id),
    CONSTRAINT uq_sales_returns_line
        UNIQUE (return_number, return_line_number),
    CONSTRAINT chk_sales_returns_quantities
        CHECK (
            returned_quantity > 0
            AND restocked_quantity >= 0
            AND rework_quantity >= 0
            AND scrapped_quantity >= 0
            AND unknown_disposition_quantity >= 0
            AND returned_quantity = (
                restocked_quantity
                + rework_quantity
                + scrapped_quantity
                + unknown_disposition_quantity
            )
        ),
    CONSTRAINT chk_sales_returns_costs
        CHECK (
            refund_unit_amount_brl >= 0
            AND return_freight_cost_brl >= 0
            AND return_processing_cost_brl >= 0
        ),
    CONSTRAINT chk_sales_returns_status
        CHECK (
            return_status IN (
                'REQUESTED',
                'RECEIVED',
                'APPROVED',
                'REJECTED'
            )
        ),
    CONSTRAINT chk_sales_returns_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_lot_allocations (
    sales_lot_allocation_id BIGINT PRIMARY KEY,
    sales_order_item_id BIGINT NOT NULL,
    production_lot_id BIGINT NOT NULL,
    allocated_quantity NUMERIC(18, 6) NOT NULL,
    allocation_method VARCHAR(30) NOT NULL,
    allocated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_lot_allocations_sales_item
        FOREIGN KEY (sales_order_item_id)
        REFERENCES raw.sales_order_items (sales_order_item_id),
    CONSTRAINT fk_sales_lot_allocations_production_lot
        FOREIGN KEY (production_lot_id)
        REFERENCES raw.production_lots (production_lot_id),
    CONSTRAINT uq_sales_lot_allocations_item_lot
        UNIQUE (sales_order_item_id, production_lot_id),
    CONSTRAINT chk_sales_lot_allocations_quantity
        CHECK (allocated_quantity > 0),
    CONSTRAINT chk_sales_lot_allocations_method
        CHECK (
            allocation_method IN (
                'DIRECT_TRACE',
                'WAREHOUSE_ALLOCATION',
                'MANUAL_ADJUSTMENT'
            )
        ),
    CONSTRAINT chk_sales_lot_allocations_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;