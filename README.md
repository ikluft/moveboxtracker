# "moveboxtracker" Project Description

The "moveboxtracker" project automates parts of moving box tracking including an inventory database
and label generation.

This is the command-line interface (CLI) for moveboxtracker.
It manages an SQLite database file containing moving) box data.
It prints labels, four to a page, including features I wanted for
tracking a move based on my experience and advice I found online.

A separate mobile app handles scanning the QR codes printed on the labels.

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
* image: storage of optional images for moving_box and item records
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
- init:   initialize new moving box database
- label:  print label(s) for specified box ids
- merge:  merge in an external SQLite database file, from another device
- dump:   dump database contents to standard output
- db:     low-level database access subcommands

### init subcommand

Before a database can be used, the SQLite database file needs to be initialized.
The usage is as follows:
> moveboxtracker init [-h] [--primary_user PRIMARY_USER] [--title TITLE] [--found_contact FOUND_CONTACT] DB

When created the database contains table definitions but no records in any of the tables.

### label subcommand

Printing a label from the database requires providing the database file, a box ID number and a PDF output file. From the database it will also retrieve the lost/found contact info, room name and room color code. Labels are printed duplicated 4 times on a page to have enough to place on 4 sides of a moving box. If more than one box ID number is provided, one page will be made for each set of labels. The resulting PDF file can be sent to any standard printer.
> moveboxtracker label [-h] --outdir PDFFILE DB ID [ID ...]

By default moveboxtracker generates PDF output for US Letter size pages. To use a different page size, set the MBT_PAGE_SIZE environment variable before running the script. For example, to use A3 size pages, set "export MBT_PAGE_SIZE=A3" in your shell or its rc setup script before running moveboxtracker.

### merge subcommand

The merge subcommand is not yet implemented. It will collect data from another SQLite database made by the moveboxtracker program or app into the one used by this instance. In particular this is intended as intake for data from the moveboxtracker Android app.

### dump subcommand

The dump subcommand prints out the contents of the SQLite database file. The path to the database file is a required parameter.
> moveboxtracker dump [-h] DB

### db subcommand

The db subcommand provides direct access to the database tables with create, read, update or delete (“CRUD”)
operations. 
> moveboxtracker db [-h] {batch,box,image,item,location,project,room,scan,user} {create,read,update,delete} ...

The database tables are:
* batch: batch/group of moving boxes
* box: moving box including label info
* image: images for boxes or items
* item: item inside a box
* location: location where boxes may be
* project: overall move project info
* room: room at origin & destination
* scan: box scan event on move to new location
* user: user who owns database or performs a box scan

Each of the tables supports command-line options named for fields in order to set values.
Fields are required if the database defines them with a "NOT NULL" constraint.

#### batch table

Each record in the batch table is a group of boxes moved together.
They should be added to the batch as they are loaded into the vehicle.
> moveboxtracker db batch [-h] --file DB [--timestamp TIMESTAMP] [--location LOCATION] {create,read,update,delete} [id]

#### box table

Each record in the box table is either a moving box or some other labeled item.
For the database's purposes, everything that gets tracked and has a label is simplified to be called a box.
Any labelled thing, whether or not it is actually a box, will be tracked in the database as a box.
For example, a framed picture or a chair also get a label with a "box" number.
> moveboxtracker db box [-h] --file DB [--location LOCATION] [--info INFO] [--room ROOM] [--user USER] [--image IMAGE] {create,read,update,delete} [id]

Things that go inside a box are in the item table.

#### image table

Each record in the image table describes a photo, stored in a directory named from the basename of the database
with a "-images" suffix.
It also has a hash to recognize if the same image is already in the database.
A field for the MIME type tells what kind of image it is, and allows looking up what program can display it.
Images in this table can be referenced by ID from the box or item tables.
> moveboxtracker db image [-h] --file DB [--box BOX] [--description DESCRIPTION] [--image IMAGE] {create,read,update,delete} [id]

#### item table

Each record in the item table is something that goes inside a box. Each item has a required reference to the box
that contains it, required description text and an optional reference to an image of the item.
> moveboxtracker db item [-h] --file DB [--box BOX] [--description DESCRIPTION] [--image IMAGE] {create,read,update,delete} [id]

#### location table

Each record in the location table is a place where boxes can be at any stage of a move operation.
Likely examples would be the origin, one or more storage or staging areas, and the destination.
The only field (other than the record ID number) is a text name.
The name needs only to be meaningful to the people working on the move.
> moveboxtracker db location [-h] --file DB [--name NAME] {create,read,update,delete} [id]
