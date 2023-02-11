CREATE TABLE IF NOT EXISTS box_scan (
  id INTEGER PRIMARY KEY,
  box integer NOT NULL REFERENCES moving_box (id),
  batch integer NOT NULL REFERENCES batch_move (id),
  user integer NOT NULL REFERENCES uri_user (id),
  timestamp datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS box_scan_id_index ON box_scan(id);
