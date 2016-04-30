# PiCam

_**This project is under development and the release that have been issued are only for testing purposes!**_

**PiCam** is a surveillance application designed for motion detection and content streaming 
that could run on any device (python enabled) 
that has attached at least one builtin or usb camera providing motion detection features. 
THe application is developed in python, using SimpleCV and related libraries.

python picam.py -h "localhost" -p 9079 -c "<command>"
python picam.py --host "localhost" --port 9079 --command "<command>"

start 
start server
stop 
stop server
start service on #X
stop service on #X
set property resolution=x,y on #X
set property property binarize=100 on #X
set property threshold=0.25 on camera X
set property recording_location=/tmp on #X
set property sleeptime=.005 on camera X
enable/disable property streaming on #X
enable/disable property recording on #X
enable/disable property recording_transitions on #X

    