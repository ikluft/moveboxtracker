CREATE TABLE IF NOT EXISTS location (
  id INTEGER PRIMARY KEY,
  name text NOT NULL 
);
CREATE INDEX IF NOT EXISTS location_id_index  ON location(id);
