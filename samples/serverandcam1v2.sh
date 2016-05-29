#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Start service and USB camera
python $_APP_HOME/picam.py -c "start server and start service on #1 and enable property streaming on #1 and enable property recording on #1" -i "0.0.0.0" -p 9079