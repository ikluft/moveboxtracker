CREATE TABLE IF NOT EXISTS room (
  id INTEGER PRIMARY KEY,
  name text UNIQUE NOT NULL,
  color text NOT NULL 
);
CREATE INDEX IF NOT EXISTS room_id_index  ON room(id);
