#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Start server instance - will not return you the prompt in console (CTRL ^C mean end of server execution)
python $_APP_HOME/picam.py -c "start server" -i "0.0.0.0" -p 9079