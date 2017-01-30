# PiCam

**PiCam** is a surveillance application designed for motion detection and content streaming. 
The application has been designed for Raspberry Pi but could run on any system (most likely 
Linux systems) that has attached cameras and has in-place all software prerequisites.
 
The application is developed in python and uses OpenCV and PiCamera libraries and all related components.

The application has been tested on **Raspberry Pi** **v2** and **v3**, running **Jessie** and **Clue** 
Linux distributions and using _Pi_ and _USB_ cameras (both connected to the RPi device or individually).

In order to run the application you have to be sure that your environment has all necessary libraries and 
software packages. Just try to execute the following commands: 
```shell
> sudo apt-get update
> sudo apt-get install python-opencv python-picamera python-scipy python-numpy python-pygame
```

The application has been designed to work in client-server mode in order to control and to command the 
cameras remotely. The application accepts three option to customize the execution or you can specify 
directly the command, aggregating all input parameters into a specific command:
```shell
> python picam.py init server
or 
> python picam.py "init server"
```
This command will start the server and will keep the prompt until a client command will be received 
to stop teh server or until the `Ctrl ^C` keyboard signal will be received.

As soon as the server is started in a separate terminal you can run the client module with a specific 
command: for example you can start the USB camera as follow:
```shell
> python picam.py "start service on #1"
> python picam.py "enable property CameraStreaming on #1"
```
So, this command will start the first USB camera and also will activate the streaming function. 

Because this application is able to control both USB and Pi cameras it is was defined a convention to 
manipulate attached camera to a Pi: so, USB camera are called using #1 to #4 (or greater, depends how 
many USB ports has your RPi device) and always camera #0 is the Pi camera attached on board.

When the PiCam server is started by default will use **9079** TCP port. In case you want to specify a 
specific port you have to use `-p` or `--port` options (the last one is considered the long option 
which needs an argument be followed by an equal sign (`=`)). The streaming ports will be selected 
by PiCam server component, starting from server PCT port and increment it for each camera (considering 
camera index).
In case you want to secure the access of PiCam server and to allow clients to run only from the local 
host you can specify the interface name using `-i` or `--interface` options. By default the server starts 
on _loopback_ interface so the clients could be instantiated only from service host. In case the client 
module is launched from a different machine you can refer server module by specifying the host name using 
`-h` or `--host` options.
If the application parameters are used (to specify the interface, host or the port) you have to specify the 
input command using `-c` or `--command` options. If no input option is used you can specify the command as 
a single parameter under double-quotes or as a list of parameters.
If you want to start **picam** application using a configuration file you have to specify one of the options 
`-f` or `--file` with a valid file path. The configuration might include commands separated by end of line 
or _JSON_ configuration. For command file the comment lines could be specified by prefixing the line with 
`#` character and empty lines will be ignored. _JSON_ configuration file describes a _JSON_ file format 
containing all **picam** properties described below. A sample _JSON_ configuration file is show in 
samples/config folder. 

The commands accepted by PiCam client and server components have been defined around to a simple grammar that 
contains only three elements:
 - **subject** - the corresponding values are: 
   - **server** = PiCam server instance, 
   - **service** = camera service (when a camera becomes active means a service identified by camera #id has 
     been started), 
   - **property** = camera or related services property (see the list of implemented properties, documented 
     below)
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
   - **load** = ask server to load a _JSON_ configuration file
   - **save** = ask server component to save current services configuration into a _JSON_ file
 - **properties** - possible values are: 
   - **CameraStreaming** = activate/de-activate streaming service for a specific camera (by default the camera 
     does not start with active streaming channel), 
   - **CameraResolution** = set camera resolution (by default the resolution for any attached camera is 640x480, 
   - **CameraFramerate** = set camera framerate (no default value is used, the camera uses the framerate set by 
     default by manufacturer), 
   - **CameraSleeptime** = sleeping time between two frames (it could be considered a second framerate but provided 
     by the application), 
   - **CameraMotion** = activate/de-activate motion detection (by default any activated camera/service will use start 
     motion detection service), 
   - **MotionContour** = activate/de-activate to draw a contour for detected motion on each camera frame (by default 
     it is active), 
   - **MotionThreshold** = set the motion detection threshold for vieweing and recording; any motion 'volume' over 
     this value will be shown marked and/or recorded, 
   - **CameraRecording** = activate/de-activate camera recording (image or video format); by default the option is disabled, 
   - **RecordingFormat** = set the recording format for camera recording function; the options are `image` or 
   `video` (default value is _image_), 
   - **RecordingLocation** = set location for the file(s) that will be created by recording service, 
   - **StreamingPort** = set streaming port, 
   - **StreamingSleeptime** = set streaming sleeping time between displayed frames.
 - **articles** - used target indicators are: **to**, **at**, **on**, **in**, **@**. After the article you have to specify 
   the camera target (#0, #1, .. - so the camera target is the camera index having `#` prefix).

**Note**: Usage of any `MotionRecording**` property will activate automatically `CameraMotion`service. 

With three elements you can compose any command (the order of elements is arbitrary) that could run in client interface. 
For instance if you want to start the Pi camera you can define and run one of the following commands:
```shell
> start service on #0 
or 
> service start on #0 
or 
> on #1 start service
```

In order to execute more commands through one single client call you can concatenate them using **and** operator (see the examples below).

For more details please run `picam.py --help`

If you want to start using this application you have to perform the following steps:

1. Install prerequisites: `sudo apt-get update && sudo apt-get install python-pip python-opencv python-picamera ipython python-scipy python-numpy python-pygame python-setuptools` 
2. Download latest release file (`clue-picam.deb` published on __GitHub__) and install it using __dpkg__ 
   command: `sudo dpkg -i clue-picam.deb`. **Attention!** Debian package will not install prerequisites, 
   do it manually!
   As an alternative download `picam.py` and `__init__.py` files and store it somewhere on the file system, 
   into a dedicated folder (e.g. `/opt/picam`). Afterwards you need to provide _exec_ permission to both python 
   source files: `cd /opt/picam ; chmod +x pycam.py __init__.py`
3. Open a shell console and execute the following command to start the server and also one of the cameras 
   (including streaming service): `pycam.py "init server and start service on #1 or enable property CameraStreaming on #1"`. 
   In case you have attached a Pi camera replace `#1` with `#0`. If you installed release file user `/opt/clue/bin/picacm` 
   binary instead direct call of `picam.py`
4. Open a browser and check `http://RPiHostname:9081` for USB camera or `http://RPiHostname:9080` for Pi camera
5. (Optional) If you want to start the second USB camera you have to execute the following command: 
    `pycam.py "start service on #2 or enable property CameraStreaming on #2"`
6. (Optional) If you want to run motion detection for the first camera you need to open another shell console and 
   to execute the following command: `pycam.py "enable property CameraRecording on #1"`. **Attention!** it will 
   store image samples in `/tmp` folder. _Please notice that **CameraRecording** activates also **CameraMotion** 
   property. 
7. (Optional) If you want to change the default location where the motion detection samples are store execute the 
   following command: `pycam.py "set property RecordingLocation=/mnt/data on #1"`.
8. (Optional) If you want to see the PiCam server configuration and all activates service just run `pycam.py server status`. 
   This client command will interrogate the server from localhost, if you want to interrogate a remote server just 
   use the command line option described before (`-c` to aggreate the command into one single text and `-h` 
   to specifiy the server hostname)


Below are described the common use-cases for **PiCam** usage:

1. Start server component
```shell
> picam server init
> picam init server
> picam -c "server init"
> picam --command="server init"
> picam -f /tmp/startup.json"
> picam --file=/tmp/startup.json"
> picam --file=/tmp/startup.cfg"
```

2. Load server configuration (when the file is not specify it will load the configuration from /opt/clue/etc/picam.cfg)
```shell
> picam server load
> picam server load from /tmp/startup.json
> picam -c "server load"
> picam -c "server load from /tmp/startup.json"
> picam -c "server load from /tmp/startup.cfg"
```

3. Start first USB camera
```shell
> picam start service on c1
> picam -c "start service on #1"
```

4. Start Streaming over USB camera
```shell
> picam enable property CameraStreaming on cam1
> picam -c "enable property CameraStreaming on #1"
```

5. Start Motion Detection over USB camera and activate also the recording function to store movies
```shell
> picam enable property CameraMotion on c1 and enable property CameraRecording on c1 and set property RecordingFormat=video on c1
> picam -c "enable property CameraMotion on #1 and enable property CameraRecording on c1 and set property RecordingFormat=video on c1"
```

6. Stop remotely Streaming property for remote USB camera
```shell
> picam disable property CameraStreaming on cam1
> picam -c "disable property CameraStreaming on #1" -h 192.168.1.100
```

7. Save server configuration (when the file is not specify it will save the configuration in /opt/clue/etc/picam.cfg)
```shell
> picam save server
> picam -c "save server"
> picam server save in /tmp/startup.json
> picam -c "save server in /tmp/startup.json"
> picam -c "save server in /tmp/startup.json" -h 10.10.10.100
```

8. Stop server instance
```shell
> picam server shutdown
> picam -c "shutdown server"
> picam -c "server shutdown"
> picam -c "shutdown server" -h 10.10.10.100 -p 9079
```

9. Others: returns (1) server Echo message (including server version, module names, etc.), (2) server status , (3) client version
```shell
> picam server echo
> picam server status
> picam --version
```
