BEGIN;

CREATE TABLE IF NOT EXISTS raw.production_orders (
    production_order_id BIGINT PRIMARY KEY,
    production_order_number VARCHAR(30) NOT NULL UNIQUE,
    product_id INTEGER NOT NULL,
    plant_id SMALLINT NOT NULL,
    production_line_id SMALLINT NOT NULL,
    bom_id INTEGER NOT NULL,
    planned_quantity NUMERIC(18, 6) NOT NULL,
    planned_start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    actual_start_at TIMESTAMPTZ,
    actual_end_at TIMESTAMPTZ,
    order_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_production_orders_product
        FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT fk_production_orders_plant
        FOREIGN KEY (plant_id)
        REFERENCES raw.plants (plant_id),
    CONSTRAINT fk_production_orders_line
        FOREIGN KEY (production_line_id)
        REFERENCES raw.production_lines (production_line_id),
    CONSTRAINT fk_production_orders_bom
        FOREIGN KEY (bom_id)
        REFERENCES raw.bill_of_materials (bom_id),
    CONSTRAINT chk_production_orders_quantity
        CHECK (planned_quantity > 0),
    CONSTRAINT chk_production_orders_planned_dates
        CHECK (planned_end_date >= planned_start_date),
    CONSTRAINT chk_production_orders_actual_dates
        CHECK (
            actual_end_at IS NULL
            OR (
                actual_start_at IS NOT NULL
                AND actual_end_at >= actual_start_at
            )
        ),
    CONSTRAINT chk_production_orders_status
        CHECK (
            order_status IN (
                'PLANNED',
                'RELEASED',
                'IN_PROGRESS',
                'COMPLETED',
                'CANCELLED'
            )
        ),
    CONSTRAINT chk_production_orders_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.production_lots (
    production_lot_id BIGINT PRIMARY KEY,
    production_order_id BIGINT NOT NULL UNIQUE,
    lot_code VARCHAR(40) NOT NULL UNIQUE,
    manufactured_date DATE NOT NULL,
    released_date DATE,
    produced_quantity NUMERIC(18, 6) NOT NULL,
    good_quantity NUMERIC(18, 6) NOT NULL,
    scrap_quantity NUMERIC(18, 6) NOT NULL,
    reworked_quantity NUMERIC(18, 6) NOT NULL,
    lot_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_production_lots_order
        FOREIGN KEY (production_order_id)
        REFERENCES raw.production_orders (production_order_id),
    CONSTRAINT chk_production_lots_quantities
        CHECK (
            produced_quantity >= 0
            AND good_quantity >= 0
            AND scrap_quantity >= 0
            AND reworked_quantity >= 0
            AND produced_quantity = good_quantity + scrap_quantity
            AND reworked_quantity <= produced_quantity
        ),
    CONSTRAINT chk_production_lots_release_date
        CHECK (
            released_date IS NULL
            OR released_date >= manufactured_date
        ),
    CONSTRAINT chk_production_lots_status
        CHECK (
            lot_status IN (
                'IN_PROCESS',
                'QUALITY_HOLD',
                'RELEASED',
                'CLOSED'
            )
        ),
    CONSTRAINT chk_production_lots_released_quantity
        CHECK (
            lot_status NOT IN ('RELEASED', 'CLOSED')
            OR good_quantity > 0
        ),
    CONSTRAINT chk_production_lots_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.production_material_consumption (
    material_consumption_id BIGINT PRIMARY KEY,
    production_order_id BIGINT NOT NULL,
    component_id INTEGER NOT NULL,
    component_cost_id BIGINT NOT NULL,
    movement_timestamp TIMESTAMPTZ NOT NULL,
    movement_type VARCHAR(30) NOT NULL,
    quantity NUMERIC(18, 6) NOT NULL,
    actual_unit_cost_brl NUMERIC(18, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_material_consumption_order
        FOREIGN KEY (production_order_id)
        REFERENCES raw.production_orders (production_order_id),
    CONSTRAINT fk_material_consumption_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT fk_material_consumption_cost
        FOREIGN KEY (component_cost_id)
        REFERENCES raw.component_cost_history (component_cost_id),
    CONSTRAINT chk_material_consumption_type
        CHECK (
            movement_type IN (
                'ISSUE',
                'RETURN_TO_STOCK'
            )
        ),
    CONSTRAINT chk_material_consumption_quantity
        CHECK (quantity > 0),
    CONSTRAINT chk_material_consumption_cost
        CHECK (actual_unit_cost_brl > 0),
    CONSTRAINT chk_material_consumption_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.production_conversion_costs (
    conversion_cost_id BIGINT PRIMARY KEY,
    production_order_id BIGINT NOT NULL,
    cost_date DATE NOT NULL,
    cost_type VARCHAR(30) NOT NULL,
    actual_hours NUMERIC(14, 6),
    hourly_rate_brl NUMERIC(14, 4),
    actual_cost_brl NUMERIC(18, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_production_conversion_costs_order
        FOREIGN KEY (production_order_id)
        REFERENCES raw.production_orders (production_order_id),
    CONSTRAINT chk_production_conversion_costs_type
        CHECK (
            cost_type IN (
                'DIRECT_LABOR',
                'MACHINE',
                'OVERHEAD',
                'REWORK_LABOR',
                'REWORK_MACHINE'
            )
        ),
    CONSTRAINT chk_production_conversion_costs_values
        CHECK (
            actual_cost_brl >= 0
            AND (actual_hours IS NULL OR actual_hours >= 0)
            AND (hourly_rate_brl IS NULL OR hourly_rate_brl >= 0)
        ),
    CONSTRAINT chk_production_conversion_costs_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.production_quality_events (
    quality_event_id BIGINT PRIMARY KEY,
    production_order_id BIGINT NOT NULL,
    component_id INTEGER,
    event_timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    quantity_affected NUMERIC(18, 6) NOT NULL,
    reason_code VARCHAR(30) NOT NULL,
    event_description VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_production_quality_events_order
        FOREIGN KEY (production_order_id)
        REFERENCES raw.production_orders (production_order_id),
    CONSTRAINT fk_production_quality_events_component
        FOREIGN KEY (component_id)
        REFERENCES raw.components (component_id),
    CONSTRAINT chk_production_quality_events_type
        CHECK (
            event_type IN (
                'SCRAP',
                'REWORK',
                'QUALITY_HOLD'
            )
        ),
    CONSTRAINT chk_production_quality_events_quantity
        CHECK (quantity_affected > 0),
    CONSTRAINT chk_production_quality_events_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;