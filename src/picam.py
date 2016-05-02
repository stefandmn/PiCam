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
		# Validate camera id input parameter
		if c_id is not None and str(c_id).startswith('#'):
			c_id = int(filter(str.isdigit, c_id))
		if c_id is None or not isinstance(c_id, int) or c_id < 0:
			raise RuntimeError('Invalid camera identifier: ' + c_id)
		# Initialize threading options
		threading.Thread.__init__(self)
		self.threadID = c_id
		self.name = "Camera #" + str(c_id)
		self._stop = threading.Event()
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
				self._camera = SimpleCV.Camera(self.id - 1, {'width':self.resolution[0],'height':self.resolution[1]}, threaded=False)
		else:
			if self.id <= 0:
				self._camera = picamera.PiCamera()
			else:
				self._camera = SimpleCV.Camera(self.id - 1)
		self.log("Service has been initialized")
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
		if self._stream is not None:
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
		self.log("Service has been stopped")

	#Method: stopped
	def stopped(self):
		return self._stop.isSet()

	#Method: log
	def log(self, data):
		print "%s | %s > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), self.name, str(data))

	#Method: start
	def run(self):
		self._exec = True
		# Initiate streaming channel
		if self.streaming:
			hostandport = '0.0.0.0:' + str(self.s_port + self.id)
			self._stream = SimpleCV.JpegStreamer(hostandport)
			self.log("Streaming started on " + hostandport)
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


#Class: CmdServer
class CmdServer:
	#Global variables
	_cameras = {}

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
		except IOError as ioerr:
			self.log(['Server binding failed:', ioerr])
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
	def log(self, data, socket=None, both=False):
		if data is not None:
			if isinstance(data, list):
				message = ''
				for obj in data:
					print "TEST: [%s]" %str(obj)
					if isinstance(obj, BaseException):
						part = str(obj)
						if part is None or part.strip() == '':
							part = type(obj).__name__
						message += ' ' + part
					else:
						message += ' ' + str(obj)
				message = message.strip()
			else:
				message = str(data)
			if (socket is None) or (socket is not None and both):
				print "%s | Server > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), message)
			if socket is not None:
				socket.sendall(message)

	#Method: run
	def run(self):
		try:
			# Mark server execution as started
			self._exec = True
			self.log("PiCam has been started and waiting for client requests..")
			# Run the infinite loop
			while self._exec:
				# Get client connection
				connection, address = self._socket.accept()
				self.log("Connection from: " +str(address))
				# Process client request
				try:
					# Receive data from client and process it
					command = connection.recv(1024)
					if not command:
						break
					else:
						# Instantiate client structure to detect the action and subject
						self.log("Receiving command: " + str(command))
						data = CmdData(command)
						# Action and subject evaluation
						if data.action == 'stop' and data.subject == 'server':
							self.runStopServer(connection)
						if data.action == 'start' and data.subject == 'service':
							self.runStartService(connection, data.target)
						if data.action == 'stop' and data.subject == 'service':
							self.runStopService(connection, data.target)
						if (data.action == 'set' or data.action == 'enable' or data.action == 'disable') and data.subject == 'property':
							self.runSetProperty(connection, data.property, data.target)
						connection.sendall(".")
					connection.close()
				except StandardError as stderr:
					if connection is not None:
						self.log(["Application error:", stderr], connection, True)
						connection.close()
					else:
						self.log(["Application error:", stderr])
			# Close connection and log channel
			self._socket.close()
		except KeyboardInterrupt:
			print
			self.log('Server interrupted by user control')
			self.runStopServer(None)
			sys.exit(2)
		except BaseException as baseerr:
			self.log(["Server error:", baseerr])
			self.runStopServer(None)
			sys.exit(6)
		self.log("PiCam stopped.\n")

	#Method: runStopServer
	def runStopServer(self, connection):
		# Stop to receive client request
		self.log("PiCam Server shutting down", socket=connection, both=True)
		self.stop()
		time.sleep(1)
		# Kill camera's threads
		if self._cameras:
			keys = self._cameras.keys()
			for key in keys:
				try:
					self.runStopService(connection, key)
					time.sleep(1)
				except BaseException as baseerr:
					self.log(["Error stopping service on camera", key , ":", baseerr])

	#Method: runStartService
	def runStartService(self, connection, target):
		if target is not None:
			if target in self._cameras:
				self.log("Camera " + target + " is already started", socket=connection, both=True)
			else:
				if target is not None:
					camera = Camera(target)
					camera.start()
					self._cameras[target] = camera
					self.log("Camera " + target + " has been started", socket=connection)
				else:
					self.log("Camera identifier could not be detected", socket=connection, both=True)
		else:
			self.log("Camera identifier was not specified", socket=connection, both=True)

	#Method: runStopService
	def runStopService(self, connection, target):
		if target is not None:
			if target in self._cameras:
				camera = self._cameras[target]
				camera.stop()
				del camera
				del self._cameras[target]
				self.log("Camera " + target + " has been stopped", socket=connection)
			else:
				self.log("Camera " + target + " was not yet started", socket=connection, both=True)
		else:
			self.log("Camera could not be identified to stop service", socket=connection, both=True)

	#Method: runSetProperty
	def runSetProperty(self,  connection, property, target):
		self.log("Setting property '" + property + "' on camera " + target, socket=connection, both=True)


#Class: CmdClient
class CmdClient:

	#Constructor
	def __init__(self, host='127.0.0.1', port=9079):
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

	#Method: getServerAddress
	def getServerAddress(self):
		return self._host + ":" + str(self._port)

	#Method: connect
	def run(self, data):
		try:
			# Generate command received from standard input
			command = data.getTextCommand()
			# Send the command to server component
			if command is not None:
				try:
					client.log("Sending command: " + command)
					_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
					_socket.connect((self._host, self._port))
					_socket.sendall(command)
					while True:
						answer = _socket.recv(1024)
						if answer != '.' and answer != '':
							self.log(answer, True)
							if answer.endswith('.'):
								break
						else:
							break
					_socket.close()
				except IOError as ioerr:
					self.log(['Client connection failed:', ioerr])
					sys.exit(1)
			else:
				self.log("Input command is null or can not be translated")
				sys.exit(1)
		except BaseException as baseerr:
			self.log(["Client error:", baseerr])
			sys.exit(6)

	#Method: log
	def log(self, data, server=False):
		if data is not None:
			if isinstance(data, list):
				message = ''
				for obj in data:
					if isinstance(obj, BaseException):
						part = str(obj)
						if part is None or part.strip() == '':
							part = type(obj).__name__
						message += ' ' + part
					else:
						message += ' ' + str(obj)
				message = message.strip()
			else:
				message = str(data)
			if not server:
				print "%s | Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), message)
			else:
				print "%s | Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), message)


#Class: CmdData
class CmdData:
	_actions = ['start', 'stop', 'set', 'enable', 'disable']
	_subjects = ['server', 'service', 'property']
	_properties = ['streaming', 'recording', 'recording_transitions', 'resolution', 'binarize', 'threshold', 'recording_location', 'sleeptime']
	_targetpreps = ['@', 'at', 'on', 'in', 'to']

	#Constructor
	def __init__(self, command):
		self.action = None
		self.subject = None
		self.location = None
		self.property = None
		self.target = None
		# Validate input command and parse it
		if command is not None and command != '':
			data = command.split(' ')
			self._parse(data)
		else:
			raise RuntimeError("Invalid or null client command")
		# Validate obtained data structure
		if (self.action == "start" or self.action == "stop") and not (self.subject == "server" or self.subject == "service"):
			raise RuntimeError("Invalid subject of start/stop action: " + self.subject)
		elif (self.action == "set" or self.action == "enable" or self.action == "disable") and self.subject != "property":
			raise RuntimeError("Invalid action for property action: " + self.action)
		elif self.subject == 'server' and self.target is not None:
			raise RuntimeError("Invalid subject for the specified target: "  + self.subject)
		elif self.action is None or self.action == '':
			raise RuntimeError("Action can not be null")
		elif self.subject is None or self.subject == '':
			raise RuntimeError("Subject can not be null")

	#Method: _parse
	def _parse(self, data):
		if data is not None and data != []:
			if data[0].strip() in self._actions:
				self.action = data[0].strip()
				del data[0]
				self._parse(data)
			elif data[0].strip() in self._subjects:
				self.subject = data[0].strip()
				del data[0]
				if self.subject == self._subjects[2]:
					index = None
					useprep = list(set(self._targetpreps) & set(data))
					useaction = list(set(self._actions) & set(data))
					if useprep:
						index = data.index(useprep[0])
					if useaction and (index is None or data.index(useaction[0]) < index):
						index = data.index(useaction[0])
					if index >= 0:
						self.property = ' '.join( data[0:index] ).strip()
						del data[0:index]
					else:
						self.property = ' '.join( data ).strip()
						del data[:]
					if not self.property.split('=')[0].strip() in self._properties:
						raise RuntimeError("Invalid property: " + self.property.split('=')[0].strip())
				self._parse(data)
			elif data[0].strip() in self._targetpreps:
				del data[0]
				self.target = '#' + filter(str.isdigit, data[0].strip())
				del data[0]
				self._parse(data)
			else:
				raise RuntimeError("Invalid command part: " + data[0].strip())

	#Method: getTextCommand
	def getTextCommand(self):
		outcmd = None
		if self.action is not None and self.subject is not None:
			outcmd = self.action + " " + self.subject
			if self.subject == self._subjects[2]:
				outcmd += " " + self.property
		if self.target is not None:
			outcmd += " on " + self.target
		return outcmd

	#Method: getTargetId
	def getTargetId(self):
		if self.target is not None:
			return int(filter(str.isdigit, self.target))
		else:
			return None


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
	# Instantiate Client module, validate command and send it to the server (or start the server component)
	if host is not None or (port is not None and port > 0):
		client = CmdClient(host, port)
	else:
		client = CmdClient()
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if command is None or command == '':
		command = ' '.join(sys.argv[1:])
	# Instantiate Data module and parse (validate) input command
	try:
		data = CmdData(command)
		# Start server or client module (depending by the sibject providing in the command line)
		if data.action == "start" and (data.subject == "server" or data.subject is None):
			if host is not None or (port is not None and port > 0):
				server = CmdServer(host, port)
			else:
				server = CmdServer()
			server.run()
			sys.exit(0)
		else:
			# Send command to server
			client.log("PiCam is calling " + client.getServerAddress())
			client.run(data)
			sys.exit(0)
	except BaseException as baseerr:
		client.log(["Client error:", baseerr])
		sys.exit(1)