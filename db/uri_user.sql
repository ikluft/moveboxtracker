CREATE TABLE IF NOT EXISTS uri_user (
  id INTEGER PRIMARY KEY,
  name text NOT NULL 
);
CREATE INDEX IF NOT EXISTS uri_user_id_index ON uri_user(id);
