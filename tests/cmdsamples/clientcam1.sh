#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Start service on Pi camera - the command will return you the prompt (can be run from other machine if the server not started from loopback interface)
python $_APP_HOME/picam.py "start service on #1 and enable property CameraStreaming on #1" -h 192.168.100.100 -p 9079