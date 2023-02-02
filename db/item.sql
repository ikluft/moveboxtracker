CREATE TABLE IF NOT EXISTS item (
  id integer INTEGER PRIMARY KEY,
  box integer NOT NULL REFERENCES moving_box (id),
  description text NOT NULL,
  image blob
);
CREATE INDEX IF NOT EXISTS item_id_index  ON item(id);