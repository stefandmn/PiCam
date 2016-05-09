# PiCam

**PiCam** is a surveillance application designed for motion detection and content streaming. The application has been designed for Raspberry Pi but could run on any system (most likely Linux systems) that has attached cameras and has in-place all software prerequisites.
 
The application is developed in python and uses OpenCV and PiCamera libraries and all related components.

The application has been tested on **Raspberry Pi 2** over **Jessie** distribution and with Pi and USB cameras (both connected to to the RPi device or individually).

In order to run the application you just to be sure that your environment has installed all necessary libraries and software packages. To do that, try to execute the following commands:
`sudo apt-get update`
`sudo apt-get install python-pip python-opencv python-picamera ipython` 
`sudo apt-get install python-scipy python-numpy python-pygame python-setuptools`

The application has been designed to work in client-server mode in order to control and to command the cameras remotely. The application accepts three option to customize the execution or you can specify directly the command, aggregating all input parameters into a specific command:
`> python picam.py start server` or `> python picam.py "start server"`
This command will start the server and will keep the prompt until a client command will be received to stop teh server or until the `Ctrl ^C` keyboard signal will be received.

As soon as the server is started in a separate terminal you can run the client module with a specific command: for example you can start the USB camera as follow:
`> python picam.py "start service on #1"`
`> python picam.py "enable property streaming on #1"`
So, this command will start the first USB camera and also will activate the streaming function. 

Because this application is able to control both USB and Pi cameras it is was defined a convention to manipulate attached camera to a Pi: so, USB camera are called using #1 to #4 (or greater, depends how many USB ports has your RPi device) and always camera #0 is the Pi camera attached on board.

When the PiCam server is started by default will use **9079** TCP port. In case you want to specify a specific port you have to use `-p` or `--port` options (the last one is considered the long option which needs an argument be followed by an equal sign ('=')). The streaming ports will be selected by PiCam server component, starting from server PCT port and increment it for each camera (considering camera index)
In case you want to secure the access of PiCam server and to allow clients to run only from the local host you can specify the interface name using `-h` or `--host` options.
If one of these parameters are used (to specify the interface or the server port) the input command have to be specified using `-c` or `--command` options.

The commands accepted by PiCam client and server components have been defined around to a simple grammar that should contain only three elements:
- **subject** - accepted values are: **server**, **service**, **property**
- **action** (verbs) - the used values are: **start**, **stop**, **set**, **enable**, **disable**
- **properties** (or complements) - possible values are: **streaming**, **recording**, **resolution**, **threshold**, **location**, **sleeptime**
- **articles** - accepted values are: **to**, **at**, **on**, **in**, **@**. After the article you have to specify the camera target (#0, #1, .. - so the camera target is the camera index having `#` prefix).

With three elements you can compose any command - specifying them in any order - that could be run in client interface. For instance if you want to start the Pi camera you can define and run one of the following commands:
`start service on #0`
        or
`service start on #0`
        or
`on #1 start service`

In order to execute more commands through one single client call you can concatenate them using **and** operator.

For more details please run `picam.py --help`

if anyone wants to use this application should perform the following steps:

1. Download `picam.py` file and store somewhere on the file system
2. (Optional) Add *execute* permission to this file: `chmox +x pycam.py`
3. Install prerequisites
3.1. `sudo apt-get update`
3.2. `sudo apt-get install python-pip python-opencv python-picamera ipython` 
3.3. `sudo apt-get install python-scipy python-numpy python-pygame python-setuptools`
4. Open a shell console and execute the following command: `pycam.py "start server and start service on #1 or enable property streaming on #1"`. In case you have attached a Pi camera replace `#1` with `#0`
5. Open a browser and check `http://RPiHostOrIP:9081` for USB camera or `http://RPiHostOrIP:9080` for Pi camera
6. Open another shell console and execute 
7. (Optional) if you have a second USB camera execute the follwing command: `pycam.py "start service on #2 or enable property streaming on #2"`
8. (Optional) If you want to run first camera with motion detection you have to execute the following command: `pycam.py "enable property recording on #1"`. **Attention!** it will store image samples in /tmp. 
9 (Optional) If you want to change the default location where the motion detection samples are store execute the following command: `pycam.py "set property location=/mnt/data on #1"`.
