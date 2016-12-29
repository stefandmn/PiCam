# PiCam

**PiCam** is a surveillance application designed for motion detection and content streaming. The application has been designed for Raspberry Pi but could run on any system (most likely Linux systems) that has attached cameras and has in-place all software prerequisites.
 
The application is developed in python and uses OpenCV and PiCamera libraries and all related components.

The application has been tested on **Raspberry Pi 2** over **Jessie** distribution and with Pi and USB cameras (both connected to the RPi device or individually).

In order to run the application you have to be sure that your environment has all necessary libraries and software packages. Just try to execute the following commands: `sudo apt-get update && sudo apt-get install python-pip python-opencv python-picamera ipython python-scipy python-numpy python-pygame python-setuptools`

The application has been designed to work in client-server mode in order to control and to command the cameras remotely. The application accepts three option to customize the execution or you can specify directly the command, aggregating all input parameters into a specific command:
`> python picam.py init server` or `> python picam.py "init server"`
This command will start the server and will keep the prompt until a client command will be received to stop teh server or until the `Ctrl ^C` keyboard signal will be received.

As soon as the server is started in a separate terminal you can run the client module with a specific command: for example you can start the USB camera as follow:
`> python picam.py "start service on #1"`
`> python picam.py "enable property CameraStreaming on #1"`
So, this command will start the first USB camera and also will activate the streaming function. 

Because this application is able to control both USB and Pi cameras it is was defined a convention to manipulate attached camera to a Pi: so, USB camera are called using #1 to #4 (or greater, depends how many USB ports has your RPi device) and always camera #0 is the Pi camera attached on board.

When the PiCam server is started by default will use **9079** TCP port. In case you want to specify a specific port you have to use `-p` or `--port` options (the last one is considered the long option which needs an argument be followed by an equal sign (`=`)). The streaming ports will be selected by PiCam server component, starting from server PCT port and increment it for each camera (considering camera index).
In case you want to secure the access of PiCam server and to allow clients to run only from the local host you can specify the interface name using `-i` or `--interface` options. By default the server starts on _loopback_ interface so the clients could be instantiated only from service host. In case the client module is launched from a different machine you can refer server module by specifying the host name using using `-h` or `--host` options.
If the application parameters are used (to specify the interface, host or the port) you have to specify the input command using `-c` or `--command` options. If no input option is used you can specify the command as a single parameter under double-quotes or as a list of parameters.
If you want to start **picam** application using a configuration file you have to specify one of the options `-f` or `--file` with a valid file path. The configuration should include commands separated by end of line. Comment lines could be specified by prefixing the line with `#` character. Empty lines are ignored.

The commands accepted by PiCam client and server components have been defined around to a simple grammar that contains only three elements:
 - **subject** - the corresponding values are: 
   - **server** = PiCam server instance, 
   - **service** = camera service (when a camera becomes active means a service identified by camera #id has been started), 
   - **property** = camera or related services property (see the list of implemented properties, documented below)
 - **action** - the implemented actions are: 
   - **init** = start server instance, 
   - **shutdown** = stop server instance, 
   - **start** = start camera service, 
   - **stop** = stop camera service, 
   - **set** = set a camera property, 
   - **enable** = activate a camera property (or a camera service), 
   - **disable** = de-activate a camera property (or a camera service), 
   - **echo** = ask for a server echo, 
   - **status** = ask for server configuration and detail status
 - **properties** - possible values are: 
   - **CameraStreaming** = activate/de-activate streaming service for a specific camera (by default the camera does not start with active streaming channel), 
   - **CameraMotionDetection** = activate/de-activate motion detection (by default any activated camera/service will use start motion detection service), 
   - **CameraResolution** = set camera resolution (by default the resolution for any attached camera is 640x480, 
   - **CameraFramerate** = set camera framerate (no default value is used, the camera uses the framerate set by default by manufacturer), 
   - **CameraSleeptime** = sleeping time between two frames (it could be considered a second framerate but provided by the application), 
   - **MotionDetectionContour** = activate/de-activate to draw a contour for detected motion on each camera frame (by default it is active), 
   - **MotionDetectionThreshold** = set the motion detection threshold for vieweing and recording; any motion 'volume' over this value will be shown marked and/or recorded, 
   - **MotionDetectionRecording** = activate/de-activate recording (in pictures or videos) for detected motion; by default the option is enabled, 
   - **MotionRecordingFormat** = set the recording format for motion detection; the possible values could be `image` or `video` (default value is _image_), 
   - **MotionRecordingLocation** = set the recording location, 
   - **StreamingPort** = set streaming port, 
   - **StreamingSleeptime** = set streaming sleeping time between displayed frames.
 - **articles** - used target indicators are: **to**, **at**, **on**, **in**, **@**. After the article you have to specify the camera target (#0, #1, .. - so the camera target is the camera index having `#` prefix).

**Note**: Usage of any `MotionRecording**` property will activate automatically `CameraMotionDetection`service. 

With three elements you can compose any command (the order of elements is arbitrary) that could run in client interface. For instance if you want to start the Pi camera you can define and run one of the following commands:
`start service on #0` or `service start on #0` or `on #1 start service`

In order to execute more commands through one single client call you can concatenate them using **and** operator (see the examples below).

For more details please run `picam.py --help`

If you want to start to use this application you have to perform the following steps:

1. Download `picam.py` file and store it somewhere on the file system
2. (Optional) Add _execute_ permission to this file: `chmox +x pycam.py`
3. Install prerequisites: `sudo apt-get update && sudo apt-get install python-pip python-opencv python-picamera ipython python-scipy python-numpy python-pygame python-setuptools` 
4. Open a shell console and execute the following command to start the server and also one of the cameras (including streaming service): `pycam.py "init server and start service on #1 or enable property CameraStreaming on #1"`. In case you have attached a Pi camera replace `#1` with `#0`
5. Open a browser and check `http://RPiHostname:9081` for USB camera or `http://RPiHostname:9080` for Pi camera
6. (Optional) If you want to start the second USB camera you have to execute the following command: `pycam.py "start service on #2 or enable property CameraStreaming on #2"`
7. (Optional) If you want to run motion detection for the first camera you need to open another shell console and to execute the following command: `pycam.py "enable property MotionDetectionRecording on #1"`. **Attention!** it will store image samples in `/tmp` folder. _Please notice that **MotionDetectionRecording** activates also **CameraMotionDetection** property._ 
8. (Optional) If you want to change the default location where the motion detection samples are store execute the following command: `pycam.py "set property MotionRecordingLocation=/mnt/data on #1"`.
9. (Optional) If you want to see the PiCam server configuration and all activates service just run `pycam.py server status`. This client command will interrogate the server from localhost, if you want to interrogate a remote server just use the command line option described before (`-c` to aggreate the command into one single text and `-h` to specifiy the server hostname)
