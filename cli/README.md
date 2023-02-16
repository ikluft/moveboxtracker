# moveboxtracker Command-line Interface

The CLI for moveboxtracker manages an SQLite database file containing moving
box data. It prints labels, four to a page, including features I wanted for
tracking a move based on my experience and advice I found online.

## Project overview

Features of the moving box labels:
* box number for database lookup
* room name and color to help unloading at the destination
  * color coding rooms is advice I found online, making it easier for helpers
* QR code for scanning for batches of boxes in each carload or truckload
* "lost & found" contact info, just in case
* set "MBT_PAGE_SIZE" environment variable to change page size (default: Letter)

Tables in the SQLite database:
* batch_move: each batch of boxes moved, time and destination
* box_scan: code scan event for a box being entered into a move batch
* image: storage of optional images (as database blobs) for moving_box and item records
* item: description of one of multiple items in a box, optional image
* location: name of a location, such as origin, storage, destination, etc
* move_project: overall project info including title, primary user and lost&found contact
* moving_box: box info including origin/destination room, current location, optional image
* room: name of origin/destination room
* uri_user: name of a user as a namespace for URIs for scanning, who did each scan

Labels are printed with data from a query of the tables move_project, moving_box, room & uri_user.

Features of mobile app (upcoming):
* Android app
* QR code scanner using Quickie library https://github.com/G00fY2/quickie
* scans a batch of boxes into local SQLite db
* exports SQLite db for merge into central CLI-managed db
* maybe future expansion to control central db on Android if others want to help with that
* no plans for an iOS app unless others want to help with that

![example moving label printout page](doc/label-pdf-example.png "example moving label printout page")

## Command-line usage

The moveboxtracker CLI uses subcommands for different functions and database elements.
These are issued like "moveboxtracker <subcommand> <subcommand-args>"
At any level the --help parameter can show a list of subcommands and options.

The top-level subcommands are
> init                initialize new moving box database
> label               print label(s) for specified box ids
> merge               merge in an external SQLite database file, from another device
> dump                dump database contents to standard output
> db                  low-level database access subcommands

### init subcommand

Before a database can be used, the SQLite database file needs to be initialized.
The usage is as follows:
> moveboxtracker init [-h] [--primary_user PRIMARY_USER] [--title TITLE] [--found_contact FOUND_CONTACT] DB
