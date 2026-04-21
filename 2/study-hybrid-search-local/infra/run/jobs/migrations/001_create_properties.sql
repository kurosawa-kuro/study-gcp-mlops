CREATE TABLE IF NOT EXISTS properties (
    id BIGINT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    city TEXT NOT NULL,
    ward TEXT,
    price INTEGER NOT NULL CHECK (price >= 0),
    management_fee INTEGER NOT NULL DEFAULT 0 CHECK (management_fee >= 0),
    layout TEXT NOT NULL,
    area NUMERIC(8,2) NOT NULL CHECK (area > 0),
    age INTEGER NOT NULL CHECK (age >= 0),
    walk_min INTEGER NOT NULL CHECK (walk_min >= 0),
    pet BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city);
CREATE INDEX IF NOT EXISTS idx_properties_layout ON properties(layout);
CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_walk_min ON properties(walk_min);
CREATE INDEX IF NOT EXISTS idx_properties_pet ON properties(pet);
