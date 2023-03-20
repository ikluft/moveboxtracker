CREATE TABLE IF NOT EXISTS image (
  id INTEGER PRIMARY KEY NOT NULL,
  image_file text UNIQUE NOT NULL,
  crc32 integer UNIQUE NOT NULL,
  mimetype text NOT NULL,
  description text,
  timestamp datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS image_id_index  ON image(id);
