BEGIN;

CREATE TABLE IF NOT EXISTS raw.customer_segments (
    customer_segment_id SMALLINT PRIMARY KEY,
    segment_code VARCHAR(20) NOT NULL UNIQUE,
    segment_name VARCHAR(100) NOT NULL,
    segment_description VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_customer_segments_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id INTEGER PRIMARY KEY,
    customer_segment_id SMALLINT NOT NULL,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    customer_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state_code CHAR(2) NOT NULL,
    sales_region VARCHAR(20) NOT NULL,
    country_code CHAR(2) NOT NULL DEFAULT 'BR',
    customer_since DATE NOT NULL,
    inactive_date DATE,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT fk_customers_segment
        FOREIGN KEY (customer_segment_id)
        REFERENCES raw.customer_segments (customer_segment_id),
    CONSTRAINT chk_customers_sales_region
        CHECK (
            sales_region IN (
                'NORTH',
                'NORTHEAST',
                'CENTRAL_WEST',
                'SOUTHEAST',
                'SOUTH'
            )
        ),
    CONSTRAINT chk_customers_dates
        CHECK (
            inactive_date IS NULL
            OR inactive_date >= customer_since
        ),
    CONSTRAINT chk_customers_active_status
        CHECK (
            (is_active = TRUE AND inactive_date IS NULL)
            OR (is_active = FALSE AND inactive_date IS NOT NULL)
        ),
    CONSTRAINT chk_customers_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.sales_channels (
    sales_channel_id SMALLINT PRIMARY KEY,
    channel_code VARCHAR(20) NOT NULL UNIQUE,
    channel_name VARCHAR(100) NOT NULL,
    channel_description VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_sales_channels_update_dates
        CHECK (updated_at >= created_at)
);

CREATE TABLE IF NOT EXISTS raw.salespeople (
    salesperson_id SMALLINT PRIMARY KEY,
    salesperson_code VARCHAR(20) NOT NULL UNIQUE,
    salesperson_name VARCHAR(150) NOT NULL,
    sales_region VARCHAR(20) NOT NULL,
    hire_date DATE NOT NULL,
    termination_date DATE,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT chk_salespeople_sales_region
        CHECK (
            sales_region IN (
                'NORTH',
                'NORTHEAST',
                'CENTRAL_WEST',
                'SOUTHEAST',
                'SOUTH'
            )
        ),
    CONSTRAINT chk_salespeople_dates
        CHECK (
            termination_date IS NULL
            OR termination_date >= hire_date
        ),
    CONSTRAINT chk_salespeople_active_status
        CHECK (
            (is_active = TRUE AND termination_date IS NULL)
            OR (is_active = FALSE AND termination_date IS NOT NULL)
        ),
    CONSTRAINT chk_salespeople_update_dates
        CHECK (updated_at >= created_at)
);

COMMIT;