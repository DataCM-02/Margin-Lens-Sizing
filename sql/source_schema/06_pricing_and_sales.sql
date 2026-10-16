BEGIN;

CREATE TABLE IF NOT EXISTS raw.price_lists (
    price_list_id SMALLINT PRIMARY KEY,
    price_list_code VARCHAR(20) NOT NULL UNIQUE,
    price_list_name VARCHAR(100) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'BRL',
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_price_lists_currency
        CHECK (currency_code = 'BRL'),
    CONSTRAINT chk_price_lists_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.price_list_items (
    price_list_item_id BIGINT PRIMARY KEY,
    price_list_id SMALLINT NOT NULL,
    product_id INTEGER NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    list_unit_price_brl NUMERIC(18, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_price_list_items_list
        FOREIGN KEY (price_list_id)
        REFERENCES raw.price_lists (price_list_id),
    CONSTRAINT fk_price_list_items_product
        FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT uq_price_list_items_period
        UNIQUE (price_list_id, product_id, valid_from),
    CONSTRAINT chk_price_list_items_price
        CHECK (list_unit_price_brl > 0),
    CONSTRAINT chk_price_list_items_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_price_list_items_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.discount_policies (
    discount_policy_id BIGINT PRIMARY KEY,
    customer_segment_id SMALLINT NOT NULL,
    product_family_id SMALLINT NOT NULL,
    sales_channel_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    automatic_discount_limit_rate NUMERIC(9, 6) NOT NULL,
    manager_approval_limit_rate NUMERIC(9, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_discount_policies_segment
        FOREIGN KEY (customer_segment_id)
        REFERENCES raw.customer_segments (customer_segment_id),
    CONSTRAINT fk_discount_policies_family
        FOREIGN KEY (product_family_id)
        REFERENCES raw.product_families (product_family_id),
    CONSTRAINT fk_discount_policies_channel
        FOREIGN KEY (sales_channel_id)
        REFERENCES raw.sales_channels (sales_channel_id),
    CONSTRAINT uq_discount_policies_period
        UNIQUE (
            customer_segment_id,
            product_family_id,
            sales_channel_id,
            valid_from
        ),
    CONSTRAINT chk_discount_policies_rates
        CHECK (
            automatic_discount_limit_rate >= 0
            AND automatic_discount_limit_rate < 1
            AND manager_approval_limit_rate >= automatic_discount_limit_rate
            AND manager_approval_limit_rate < 1
        ),
    CONSTRAINT chk_discount_policies_dates
        CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT chk_discount_policies_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.approved_discount_exceptions (
    discount_exception_id BIGINT PRIMARY KEY,
    approval_code VARCHAR(30) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    product_family_id SMALLINT NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    approved_discount_rate NUMERIC(9, 6) NOT NULL,
    approved_by_role VARCHAR(100) NOT NULL,
    approval_reason VARCHAR(250) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_discount_exceptions_customer
        FOREIGN KEY (customer_id)
        REFERENCES raw.customers (customer_id),
    CONSTRAINT fk_discount_exceptions_family
        FOREIGN KEY (product_family_id)
        REFERENCES raw.product_families (product_family_id),
    CONSTRAINT chk_discount_exceptions_rate
        CHECK (
            approved_discount_rate >= 0
            AND approved_discount_rate < 1
        ),
    CONSTRAINT chk_discount_exceptions_dates
        CHECK (valid_to >= valid_from),
    CONSTRAINT chk_discount_exceptions_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_orders (
    sales_order_id BIGINT PRIMARY KEY,
    sales_order_number VARCHAR(30) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    salesperson_id SMALLINT NOT NULL,
    sales_channel_id SMALLINT NOT NULL,
    price_list_id SMALLINT NOT NULL,
    order_date DATE NOT NULL,
    requested_delivery_date DATE NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES raw.customers (customer_id),
    CONSTRAINT fk_sales_orders_salesperson
        FOREIGN KEY (salesperson_id)
        REFERENCES raw.salespeople (salesperson_id),
    CONSTRAINT fk_sales_orders_channel
        FOREIGN KEY (sales_channel_id)
        REFERENCES raw.sales_channels (sales_channel_id),
    CONSTRAINT fk_sales_orders_price_list
        FOREIGN KEY (price_list_id)
        REFERENCES raw.price_lists (price_list_id),
    CONSTRAINT chk_sales_orders_delivery_date
        CHECK (requested_delivery_date >= order_date),
    CONSTRAINT chk_sales_orders_status
        CHECK (
            order_status IN (
                'OPEN',
                'PARTIALLY_INVOICED',
                'INVOICED',
                'CANCELLED'
            )
        ),
    CONSTRAINT chk_sales_orders_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_order_items (
    sales_order_item_id BIGINT PRIMARY KEY,
    sales_order_id BIGINT NOT NULL,
    line_number SMALLINT NOT NULL,
    product_id INTEGER NOT NULL,
    discount_exception_id BIGINT,
    ordered_quantity NUMERIC(18, 6) NOT NULL,
    invoiced_quantity NUMERIC(18, 6) NOT NULL DEFAULT 0,
    list_unit_price_brl NUMERIC(18, 4) NOT NULL,
    discount_rate NUMERIC(9, 6) NOT NULL,
    realized_unit_price_brl NUMERIC(18, 4) NOT NULL,
    managerial_sales_tax_rate NUMERIC(9, 6) NOT NULL,
    invoice_number VARCHAR(30),
    invoice_date DATE,
    item_status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_sales_order_items_order
        FOREIGN KEY (sales_order_id)
        REFERENCES raw.sales_orders (sales_order_id),
    CONSTRAINT fk_sales_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES raw.products (product_id),
    CONSTRAINT fk_sales_order_items_exception
        FOREIGN KEY (discount_exception_id)
        REFERENCES raw.approved_discount_exceptions (discount_exception_id),
    CONSTRAINT uq_sales_order_items_line
        UNIQUE (sales_order_id, line_number),
    CONSTRAINT chk_sales_order_items_quantities
        CHECK (
            ordered_quantity > 0
            AND invoiced_quantity >= 0
            AND invoiced_quantity <= ordered_quantity
        ),
    CONSTRAINT chk_sales_order_items_prices
        CHECK (
            list_unit_price_brl > 0
            AND realized_unit_price_brl >= 0
            AND realized_unit_price_brl <= list_unit_price_brl
        ),
    CONSTRAINT chk_sales_order_items_discount
        CHECK (
            discount_rate >= 0
            AND discount_rate < 1
        ),
    CONSTRAINT chk_sales_order_items_tax
        CHECK (
            managerial_sales_tax_rate >= 0
            AND managerial_sales_tax_rate < 1
        ),
    CONSTRAINT chk_sales_order_items_invoice
        CHECK (
            (
                invoiced_quantity = 0
                AND invoice_number IS NULL
                AND invoice_date IS NULL
            )
            OR (
                invoiced_quantity > 0
                AND invoice_number IS NOT NULL
                AND invoice_date IS NOT NULL
            )
        ),
    CONSTRAINT chk_sales_order_items_status
        CHECK (
            item_status IN (
                'OPEN',
                'PARTIALLY_INVOICED',
                'INVOICED',
                'CANCELLED'
            )
        ),
    CONSTRAINT chk_sales_order_items_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;