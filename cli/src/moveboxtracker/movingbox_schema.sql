CREATE TABLE IF NOT EXISTS batch_move (
  id INTEGER PRIMARY KEY,
  timestamp datetime NOT NULL ,
  location integer NOT NULL REFERENCES location (id)
);
CREATE INDEX IF NOT EXISTS batch_move_id_index ON batch_move(id);
CREATE TABLE IF NOT EXISTS box_scan (
  id integer INTEGER PRIMARY KEY,
  box integer NOT NULL REFERENCES moving_box (id),
  batch integer NOT NULL REFERENCES batch_move (id),
  user integer NOT NULL REFERENCES url_user (id),
  timestamp datetime NOT NULL 
);
CREATE INDEX IF NOT EXISTS box_scan_id_index ON box_scan(id);
CREATE TABLE IF NOT EXISTS item (
  id integer INTEGER PRIMARY KEY,
  box integer NOT NULL REFERENCES moving_box (id),
  description text NOT NULL,
  image blob
);
CREATE INDEX IF NOT EXISTS item_id_index  ON item(id);
CREATE TABLE IF NOT EXISTS location (
  id integer INTEGER PRIMARY KEY,
  name text NOT NULL 
);
CREATE INDEX IF NOT EXISTS location_id_index  ON location(id);
CREATE TABLE IF NOT EXISTS log (
  id integer INTEGER PRIMARY KEY,
  table_name text NOT NULL ,
  field_name text NOT NULL ,
  old text,
  new text,
  timestamp datetime NOT NULL 
);
CREATE INDEX IF NOT EXISTS log_id_index  ON log(id);
CREATE TABLE IF NOT EXISTS move_project (
  primary_user integer NOT NULL REFERENCES uri_user (id),
  title text NOT NULL,
  found_contact text NOT NULL 
);
CREATE TABLE IF NOT EXISTS moving_box (
  id integer INTEGER PRIMARY KEY,
  location integer NOT NULL REFERENCES location (id),
  info text NOT NULL ,
  room integer NOT NULL REFERENCES room (id),
  user integer NOT NULL REFERENCES url_user (id),
  image blob 
);
CREATE INDEX IF NOT EXISTS moving_box_id_index  ON moving_box(id);
CREATE TABLE IF NOT EXISTS room (
  id integer INTEGER PRIMARY KEY,
  name text NOT NULL,
  color text NOT NULL 
);
CREATE INDEX IF NOT EXISTS room_id_index  ON room(id);
CREATE TABLE IF NOT EXISTS uri_user (
  id INTEGER PRIMARY KEY,
  name text NOT NULL 
);
CREATE INDEX IF NOT EXISTS uri_user_id_index ON uri_user(id);
