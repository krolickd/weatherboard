Weatherboard
============

The source code for my e-paper based weather display. This project was forked from andrewgodwin and modified:

* Using yellow E-Paper
* Imperial units
* Windows webhosting/ Heroku deployment
* Additional fields
* Icons for day/night

The project has separate folders for the sever and client applications:

* `<display/>`_ contains a basic Python script that renders an image onto the e-paper from a URL or local file
* `<server/>`_ contains the server that this script is scheduled to fetch an image from periodically, and which renders the actual weather display
