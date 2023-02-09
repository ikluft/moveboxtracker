CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY,
  table_name text NOT NULL ,
  field_name text NOT NULL ,
  old text,
  new text,
  timestamp datetime NOT NULL 
);
CREATE INDEX IF NOT EXISTS log_id_index  ON log(id);
