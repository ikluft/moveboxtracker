CREATE TABLE IF NOT EXISTS moving_box (
  id INTEGER PRIMARY KEY,
  location integer NOT NULL REFERENCES location (id),
  info text NOT NULL ,
  room integer NOT NULL REFERENCES room (id),
  user integer NOT NULL REFERENCES url_user (id),
  image blob 
);
CREATE INDEX IF NOT EXISTS moving_box_id_index  ON moving_box(id);
