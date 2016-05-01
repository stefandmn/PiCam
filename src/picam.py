#!/usr/bin/env python

import io
import os
import PIL
import sys
import time
import socket
import getopt
import datetime
import SimpleCV
import picamera
import threading


#Class: Camera
class Camera(threading.Thread):
	def __init__(self, c_id, c_resolution=(640, 480),
				 streaming=True, s_port=9080, s_sleeptime=0.1,
				 recording=False, r_binarize=100, r_threshold=0.235, r_transitions=False, r_location='/tmp'):
		# Initialize class public variables (class parameters)
		self.id = c_id
		self.resolution = c_resolution
		self.streaming = streaming
		self.s_port = s_port
		self.s_sleeptime = s_sleeptime
		self.recording = recording
		self.r_binarize = r_binarize
		self.r_threshold = r_threshold
		self.r_transitions = r_transitions
		self.r_Location = r_location
		# Initialize threading options
		threading.Thread.__init__(self)
		self.threadID = self.id
		self.name = "Camera #" + str(self.id)
		self._stop = threading.Event()
		# Initialize class private variables
		self._exec = False
		self._pframe = None
		self._nframe = None
		# Define tools
		self._camera = None
		self._stream = None
		# Identify type of camera
		if self.resolution is not None:
			if self.id <= 0:
				self._camera = picamera.PiCamera(resolution=self.resolution)
			else:
				self._camera = SimpleCV.Camera(self.id - 1, {'width':self.resolution[0],'height':self.resolution[1]})
		else:
			if self.id <= 0:
				self._camera = picamera.PiCamera()
			else:
				self._camera = SimpleCV.Camera(self.id - 1)
		self.log(self.name + " has been initialized..")
		if self.recording:
			self._pframe = self.getImage()
			self._pframe.drawText("Start monitoring @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime()), self._pframe.width - 250, self._pframe.height - 20, (255, 255, 255), 20)
			self._pframe.save(self.r_Location + os.path.sep + "photo-cam" + str(self.id).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") +".png")

	#Method: getImage
	def getImage(self):
		if isinstance(self._camera, SimpleCV.Camera):
			image = self._camera.getImage()
		else:
			bytebuf = io.BytesIO()
			self._camera.capture(bytebuf, format='jpeg', use_video_port=True)
			bytebuf.seek(0)
			image = SimpleCV.Image(PIL.Image.open(bytebuf))
		return image

	#Method: isMotion
	def isMotion(self):
		if self._nframe is not None:
			if self._pframe is not None:
				diff = (self._nframe.toGray() - self._pframe.toGray()).binarize(self.r_binarize).invert()
				mean = diff.getNumpy().mean()
				# Validate if found motion is bigger than threshold
				if mean >= self.r_threshold:
					return True
				else:
					return False
			else:
				return False
		else:
			return False

	#Method: setRecording
	def setRecording(self):
		message = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
		filename = self.r_Location + "/photo-cam" + str(self.id).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f") + ".png"
		if self.r_transitions:
			drawing = SimpleCV.DrawingLayer((self._pframe.width * 2 + 2, self._pframe.height))
			drawing.blit(self._pframe)
			drawing.blit(self._nframe, (self._pframe.width + 2, 0))
			drawing.line((self._pframe.width + 1, 0), (self._pframe.width + 1, self._pframe.height))
			cframe = self._pframe.copy().resize(self._nframe.width * 2, self._nframe.height)
			cframe.addDrawingLayer(drawing)
			cframe.drawText(message, self._nframe.width * 2 - 130, self._nframe.height - 20, (255, 255, 255), 20)
			cframe.save(filename)
		else:
			self._nframe.drawText(message, self._nframe.width - 130, self._nframe.height - 20, (255, 255, 255), 20)
			self._nframe.save(filename)

	#Method: stop
	def stop(self):
		self._exec = False
		self.streaming = False
		self.recording = False
		# Stop streaming
		self._stream.server.shutdown()
		self._stream.server.server_close()
		self._stream = None
		# For PiCamera call close method
		if isinstance(self._camera, picamera.PiCamera):
			self._camera.close()
		# Destroy Camera instance
		self._camera = None
		# Stop the thread
		self._stop.set()
		self.log(self.name + " has been stopped")

	#Method: stopped
	def stopped(self):
		return self._stop.isSet()

	#Method: log
	def log(self, data):
		print "%s | Camera > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), str(data))

	#Method: start
	def run(self):
		self._exec = True
		# Initiate streaming channel
		if self.streaming:
			iport = '0.0.0.0:' + str(self.s_port + self.id)
			self._stream = SimpleCV.JpegStreamer(iport)
			self.log(self.name + " started streaming on " + iport)
		# Run surveillance workflow
		while self._exec:
			# Capture image frame
			self._nframe = self.getImage()
			# If the streaming is active send the picture through the streaming channel
			if self._stream is not None and self.streaming == True:
				self._nframe.save(self._stream.framebuffer)
			# If motion recording feature is active identify motion and save pictures
			if self.recording:
				# Check if previous image has been captured
				if self.isMotion():
					self.setRecording()
			# Set previous image with the existing capture
			self._pframe = self._nframe
			# Sleep for couple of milliseconds and then run again
			time.sleep(self.s_sleeptime)
			self.log(self.name + "\t..running: " + str(self._exec))

#Class: CmdServer
class CmdServer:
	#Global variables
	__cameras = {}

	#Constructor
	def __init__(self, host="127.0.0.1", port=9079):
		# Set server host name and port
		self._host = host
		self._port = port
		# Validate host name
		if self._host is None or self._host == '':
			self._host = socket.gethostname()
			if self._host is None or self._host == '':
				self._host = '127.0.0.1'
		# Validate port
		if self._port is None or self._port <= 0:
			self._port = 9079
		# Instantiate server execution flag
		self._exec = False
		# Instantiate main server connection
		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# Start binding server connection
		try:
			self._socket.bind((self._host, self._port))
		except socket.error as msg:
			self.log('ERROR: Server binding failed. \n\t\tCode: ' + str(msg[0]) + '\n\t\tMessage: ' + msg[1])
			sys.exit(2)
		# Set server connection to accept only 10 connection
		self._socket.listen(10)
		self.log("PiCam started on " + self.getServerAddress())

	#Method: getServerAddress
	def getServerAddress(self):
		return self._host + ":" + str(self._port)

	#Method: stop
	def stop(self):
		self._exec = False

	#Method: log
	def log(self, data, client=False):
		if not client:
			print "%s | Server > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), str(data))
		else:
			print "%s | Client > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), str(data))

	#Method: start
	def start(self):
		# Mark server execution as started
		self._exec = True
		self.log("PiCam has been started and waiting for client requests..")
		# Start the infinite look
		while self._exec:
			try:
				conn, addr = self._socket.accept()
				self.log("Connection from: " +str(addr))
				# Receive data from client and process it
				data = conn.recv(1024)
				if not data:
					break
				else:
					# Instantiate client structure to detect the action and subject
					self.log("Request: " + str(data), True)
					client = CmdClient(data)
					client.parse()
					# Action and subject evaluation
					if client.action == 'stop' and client.subject == 'server':
						self.execStopServer(conn, client)
					if client.action == 'start' and client.subject == 'service':
						self.execStartService(conn, client)
					if client.action == 'stop' and client.subject == 'service':
						self.execStopService(conn, client)
					if (client.action == 'set' or client.action == 'enable' or client.action == 'disable') and client.subject == 'property':
						self.execSetProperty(conn, client)
				conn.close()
			except socket.error as msg:
				self.log('ERROR: Server connection failed. \n\t\tCode: ' + str(msg[0]) + '\n\t\tMessage: ' + msg[1])
			except KeyboardInterrupt:
				print
				self.log('Server interrupted by user control')
				self.stop()
		# Close connection
		self._socket.close()
		self.log("PiCam stopped.")
		print

	#Method: execStopServer
	def execStopServer(self, conn, client):
		conn.sendall("PiCam Server shutting down..")
		time.sleep(3)
		self.stop()

	#Method: execStopServer
	def execStartService(self, conn, client):
		camid = int(filter(str.isdigit, client.target))
		key = "#" + str(camid)
		if key in self.__cameras:
			conn.sendall("Camera #" + str(camid) + " is already started")
		else:
			camera = Camera(c_id=camid)
			camera.start()
			self.__cameras[key] = camera
			conn.sendall("Camera #" + str(camid) + " has been started")

	#Method: execStopServer
	def execStopService(self, conn, client):
		camid = int(filter(str.isdigit, client.target))
		key = "#" + str(camid)
		if key in self.__cameras:
			camera = self.__cameras[key]
			camera.stop()
			del camera
			del self.__cameras[key]
			conn.sendall("Camera #" + str(camid) + " has been stopped")
		else:
			conn.sendall("Camera #" + str(camid) + " was not yet started")

	#Method: execStopServer
	def execSetProperty(self, conn, client):
		camid = int(filter(str.isdigit, client.target))
		conn.sendall("Setting property '" + client.property + "' on camera #" + str(camid))


#Class: CmdClient
class CmdClient:
	_actions = ['start', 'stop', 'set', 'enable', 'disable']
	_subjects = ['server', 'service', 'property']
	_properties = ['streaming', 'recording', 'recording_transitions', 'resolution', 'binarize', 'threshold', 'recording_location', 'sleeptime']
	_targetpreps = ['@', 'at', 'on', 'in', 'to']

	#Constructor
	def __init__(self, command, host='127.0.0.1', port=9079):
		self.action = None
		self.subject = None
		self.location = None
		self.property = None
		self.target = None
		# Set server host name and port
		self._host = host
		self._port = port
		# Validate host name
		if self._host is None or self._host == '':
			self._host = socket.gethostname()
			if self._host is None or self._host == '':
				self._host = '127.0.0.1'
		# Validate port
		if self._port is None or self._port <= 0:
			self._port = 9079
		# Validate command
		if command != '' and command is not None:
			self._input = command.split(' ')
		else:
			self._input = None

	#Method: parse
	def parse(self):
		if self._input is not None and self._input != []:
			if self._input[0].strip() in self._actions:
				self.action = self._input[0].strip()
				del self._input[0]
				return self.parse()
			elif self._input[0].strip() in self._subjects:
				self.subject = self._input[0].strip()
				del self._input[0]
				if self.subject == self._subjects[2]:
					index = None
					useprep = list(set(self._targetpreps) & set(self._input))
					useaction = list(set(self._actions) & set(self._input))
					if useprep:
						index = self._input.index(useprep[0])
					if useaction and (index is None or self._input.index(useaction[0]) < index):
						index = self._input.index(useaction[0])
					if index >= 0:
						self.property = ' '.join( self._input[0:index] ).strip()
						del self._input[0:index]
					else:
						self.property = ' '.join( self._input ).strip()
						del self._input[:]
					if not self.property.split('=')[0].strip() in self._properties:
						return {'status':False, 'message':"Invalid property: " + self.property.split('=')[0].strip()}
				return self.parse()
			elif self._input[0].strip() in self._targetpreps:
				del self._input[0]
				self.target = self._input[0].strip()
				del self._input[0]
				return self.parse()
			else:
				return {'status':False, 'message':"Invalid command: " + self._input[0].strip()}
		else:
			if (self.action == "start" or self.action == "stop") and not (self.subject == "server" or self.subject == "service"):
				return {'status':False, 'message':"Invalid subject of start/stop action: " + self.subject}
			elif (self.action == "set" or self.action == "enable" or self.action == "disable") and self.subject != "property":
				return {'status':False, 'message':"Invalid action for property action: " + self.action}
			elif self.action is None or self.action == '':
				return {'status':False, 'message':"Action can not be null"}
			elif self.subject is None or self.subject == '':
				return {'status':False, 'message':"Subject can not be null"}
			else:
				return {'status':True, 'message':""}

	#Method: getTextCommand
	def getTextCommand(self):
		command = None
		if self.action is not None and self.subject is not None:
			command = self.action + " " + self.subject
			if self.subject == self._subjects[2]:
				command += " " + self.property
		if self.target is not None:
			command += " on " + self.target
		return command

	#Method: getServerAddress
	def getServerAddress(self):
		return self._host + ":" + str(self._port)

	#Method: send
	def send(self):
		# Generate command received from standard input
		command = self.getTextCommand()
		client.log("Running: " + client.getTextCommand())
		# Send the command to server component
		if command is not None:
			try:
				_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				_socket.connect((self._host, self._port))
				_socket.sendall(command)
				answer = _socket.recv(1024)
				_socket.close()
				return {'status':True, 'message':answer}
			except socket.error as msg:
				return {'status':True, 'message':'Client connection failed. \n\t\tCode: ' + str(msg[0]) + '\n\t\tMessage: ' + msg[1]}

	#Method: log
	def log(self, data, server=False):
		if not server:
			print "%s | Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), str(data))
		else:
			print "%s | Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), str(data))


def usage():
	print """
Usage: picam -c "start server" -h "localhost" -p 9079

In order to run server or client modules use the syntax:
	> picam -c "start server"
	> picam --command="start server"
= run server (using default hostname and port) using input options
	> picam start server
= run server (using default hostname and port) aggregating command from all input parameters
	> picam -c "start server" -h "10.10.10.100" -p 6400
	> picam --command="start server" --host="127.0.0.1" --port=6400
= run server (using default hostname and port) using input options
	> picam -c "start service on #1"
	> picam --command="start service on c1"
= run client to start on server camera #1. The client will connect to server using default port
	> picam enable recording on c0
= run client (using default hostname and port) aggregating command from all input parameters
	> picam -c "set parameter resolution=1280,720 on c1" -h "192.168.0.100" -p 6400
	> picam --command="set parameter resolution=1280,720 on c1" --host="127.0.0.1" --port=6400
= run client that will send the command described by a specific option to a dedicated server
	"""

if __name__=="__main__":
	# Global variables to identify input parameters
	command = None
	host = None
	port = None
	# Parse input parameters
	opts, args = getopt.getopt(sys.argv[1:], "c:h:p", ["command=", "host=", "port=", "help"])
	# Collect input parameters
	for opt, arg in opts:
		if opt in ("-c", "--command"):
			command = arg
		elif opt in ("-h", "--host"):
			host = arg
		elif opt in ("-p", "--port"):
			port = arg
		elif opt == '--help':
			usage()
			sys.exit(0)
	# If command was not specified through input options collect all input parameters and aggregate them in one single command
	if command is None or command == '':
		command = ' '.join(sys.argv[1:])
	# Instantiate Client module, validate command and send it to the server (or start the server component)
	if host is not None or (port is not None and port > 0):
		client = CmdClient(command, host, port)
	else:
		client = CmdClient(command)
	output = client.parse()
	# If the command doesn't have error, process it
	if output['status']:
		# Start server
		if client.action == "start" and (client.subject == "server" or client.subject is None):
			if client.target is not None:
				server = CmdServer(client.target.split(":")[0], int(client.target.split(":")[1]))
			else:
				if host is not None or (port is not None and port > 0):
					server = CmdServer(host, port)
				else:
					server = CmdServer()
			server.start()
		else:
			# Send command to server
			client.log("PiCam started to call " + client.getServerAddress())
			output = client.send()
			if output['status']:
				client.log(output['message'], True)
				print
			else:
				client.log("ERROR: " + output['message'])
				print
				sys.exit(1)
	else:
		client.log("ERROR: " + output['message'])
		print
		sys.exit(1)