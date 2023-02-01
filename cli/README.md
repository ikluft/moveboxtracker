moveboxtracker Command-line Interface
-------------------------------------

The CLI for moveboxtracker manages an SQLite database file containing moving
box data. It prints labels, four to a page, including features I wanted for
tracking a move based on my experience and advice I found online.

Features of the moving box labels:
* box number for database lookup
* room name and color to help unloading at the destination
  * color coding rooms is advice I found online, making it easier for helpers
* QR code for scanning for batches of boxes in each carload or truckload
* "lost & found" contact info, just in case

Tables in the SQLite database: "label" indicates data shown on labels
* batch_move: each batch of boxes moved, time and destination
* box_scan: code scan event for a box being entered into a move batch
* item: description of one of multiple items in a box, optional image
* location: name of a location, such as origin, storage, destination, etc
* log: records of table update events
* move_project: overall project info including title, primary user and lost&found contact (label)
* moving_box: box info including origin/destination room, current location, optional image (label)
* room: name of origin/destination room (label)
* uri_user: name of a user as a namespace for URIs for scanning, who did each scan (label)

Features of mobile app (upcoming):
* Android app
* QR code scanner using Quickie library https://github.com/G00fY2/quickie
* scans a batch of boxes into local SQLite db
* exports SQLite db for merge into central CLI-managed db
* maybe future expansion to control central db on Android if others want to help with that
* no plans for an iOS app unless others want to help with that

![example moving label printout page](doc/label-pdf-example.png "example moving label printout page")
