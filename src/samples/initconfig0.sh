#!/bin/bash

# Get path variables
_APP_SAMPLES=`dirname $0`
_APP_HOME=$(cd $_APP_SAMPLES/../;pwd)

# Run application base on configuration file (a file with commands)
python $_APP_HOME/picam.py -f $_APP_SAMPLES/config/startup0.cfg