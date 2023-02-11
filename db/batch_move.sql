CREATE TABLE IF NOT EXISTS batch_move (
  id INTEGER PRIMARY KEY,
  timestamp datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  location integer NOT NULL REFERENCES location (id)
);
CREATE INDEX IF NOT EXISTS batch_move_id_index ON batch_move(id);
