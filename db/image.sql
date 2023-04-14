CREATE TABLE IF NOT EXISTS image (
  id INTEGER PRIMARY KEY NOT NULL,
  image_file text UNIQUE NOT NULL,
  hash text UNIQUE NOT NULL,
  mimetype text,
  encoding text,
  description text,
  timestamp datetime NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS image_id_index  ON image(id);
