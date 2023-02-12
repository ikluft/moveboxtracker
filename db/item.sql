CREATE TABLE IF NOT EXISTS item (
  id INTEGER PRIMARY KEY,
  box integer NOT NULL REFERENCES moving_box (id),
  description text NOT NULL,
  image integer REFERENCES image (id)
);
CREATE INDEX IF NOT EXISTS item_id_index  ON item(id);
