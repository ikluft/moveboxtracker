CREATE TABLE IF NOT EXISTS move_project (
  primary_user integer NOT NULL REFERENCES uri_user (id),
  title text NOT NULL,
  found_contact text NOT NULL 
);
