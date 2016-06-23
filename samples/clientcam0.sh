#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Start service on Pi camera - the command will return you the prompt
python $_APP_HOME/picam.py "start service on #0 and set property CameraResolution=320,240 on #0 and enable property CameraStreaming on #0"