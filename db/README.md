# moveboxtracker database schema

## database entity relationship diagram
![database entity relationship diagram](moveboxtracker-erd.png)

## database table definitions
These tables are defined in the project's database.
* [batch_move](batch_move.sql): each batch of boxes moved, time and destination
* [box_scan](box_scan.sql): code scan event for a box being entered into a move batch
* [image](image.sql): storage of optional images (as database blobs) for moving_box and item records
* [item](item.sql): description of one of multiple items in a box, optional image
* [location](location.sql): name of a location, such as origin, storage, destination, etc
* [move_project](move_project.sql): overall project info including title, primary user and lost&found contact
* [moving_box](moving_box.sql): box info including origin/destination room, current location, optional image
* [room](room.sql): name of origin/destination room
* [uri_user](uri_user.sql): name of a user as a namespace for URIs for scanning, who did each scan
