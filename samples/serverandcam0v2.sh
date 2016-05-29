#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Start service and Pi camera
python $_APP_HOME/picam.py "start server and start service on #0 and set property resolution=640,480 on #0 and enable property streaming on #0 and enable property recording on #0"