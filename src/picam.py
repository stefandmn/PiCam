#!/usr/bin/python

__project__     = "Clue"
__module__      = "PiCam"
__author__      = "SDA"
__copyright__   = "Copyright (C) 2015-2016, AMSD"
__license__     = "GPL"
__version__     = "1.1.2"
__maintainer__  = "SDA"
__email__       = "damian.stefan@gmail.com"
__status__      = "Production"
__verbose__     = False


import os
import io
import cv
import sys
import time
import socket
import getopt
import datetime
import threading
import traceback
from PIL import Image
from picamera import PiCamera
from SocketServer import ThreadingMixIn, BaseRequestHandler, TCPServer
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


#Class: Camera
class Camera(threading.Thread):
	def __init__(self, c_id, c_resolution=None, c_framerate=None,
				streaming=False, s_port=9080, s_sleeptime=0.05,
				recording=False, r_threshold=1000, r_location='/tmp'):
		# Validate camera id input parameter
		if c_id is not None and str(c_id).startswith('#'):
			c_id = int(filter(str.isdigit, c_id))
		if c_id is None or not isinstance(c_id, int) or c_id < 0:
			raise RuntimeError('Invalid camera identifier: ' + c_id)
		# Initialize threading options
		threading.Thread.__init__(self)
		self.name = "Camera #" + str(c_id)
		self._stop = threading.Event()
		# Initialize class public variables (class parameters)
		self._id = c_id
		self._resolution = c_resolution
		self._framerate = c_framerate
		self._s_port = s_port
		self._s_sleeptime = s_sleeptime
		self._r_threshold = r_threshold
		self._r_location = r_location
		# Initialize class private variables
		self._exec = False
		self._lock = True
		self._frame = None
		# Define tools
		self._camera = None
		self._stream = None
		self._motion = None
		# Identify type of camera and initialize camera device
		self.setOnCamera()
		# Activate recording if was specified during initialization
		if recording:
			self._setRecording()
		else:
			self._recording = False
		if streaming:
			self._setStreaming()
		else:
			self._streaming = False
		self.log("Service has been initialized")

	#Method: getId
	def getId(self):
		return self._id

	#Method: setOnCamera
	def setOnCamera(self):
		if self._camera is None:
			try:
				self._lock = True
				if self._id == 0:
					self._camera = PiCamera()
					if self._resolution is not None:
						self._camera.resolution=self._resolution
					if self._framerate is not None:
						self._camera.framerate = self._framerate
				else:
					self._camera = cv.CaptureFromCAM(self._id - 1)
					if self._resolution is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
					if self._framerate is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Error initializing camera service:", baseerr])
		else:
			self.log("Camera service is already started")

	#Method: setOffCamera
	def setOffCamera(self):
		if self._camera is not None:
			try:
				self._lock = True
				# For PiCamera call close method
				if isinstance(self._camera, PiCamera):
					self._camera.close()
				# Destroy Camera instance
				del self._camera
				self._camera = None
			except BaseException as baseerr:
				self.log(["Error stopping camera service:", baseerr])
		else:
			self.log("Camera service is already stopped")

	#Method: getFrame
	def getFrame(self):
		return self._frame

	#Method: setFrame
	def setFrame(self):
		if not self._lock and self._camera is not None:
			if isinstance(self._camera, PiCamera):
				byte_buffer = io.BytesIO()
				self._camera.capture(byte_buffer, format='jpeg', use_video_port=True)
				byte_buffer.seek(0)
				pil = Image.open(byte_buffer)
				self._frame = cv.CreateImageHeader(self._camera.resolution, cv.IPL_DEPTH_8U, 3)
				cv.SetData(self._frame, pil.tostring())
				cv.CvtColor(self._frame, self._frame, cv.CV_RGB2BGR)
			else:
				self._frame = cv.QueryFrame(self._camera)
			cv.PutText(self._frame, "CAM " + str(self.getId()).rjust(2, '0'),(5, 15), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .35, .35, 0.0, 1, cv.CV_AA), (255, 255, 255))

	#Method: _setRecording
	def _setRecording(self):
		if self._motion is None:
			self._motion = Motion(self)
		self._recording = True

	#Method: setOnRecording
	def setOnRecording(self):
		if not self.isRecording():
			self._setRecording()
		else:
			self.log("Recording function is already enabled")

	#Method: setOffRecording
	def setOffRecording(self):
		if self.isRecording():
			self._recording = False
		else:
			self.log("Recording function is not enabled")

	#Method: isRecording
	def isRecording(self):
		return self._recording

	#Method: runRecording
	def runRecording(self):
		if self.isRecording() and self._motion is not None:
			self._motion.detect()

	#Method: _setStreaming
	def _setStreaming(self):
		try:
			self._stream = StreamServer(('0.0.0.0', self._s_port), StreamHandler, frame=self.getFrame(), sleeptime=self.getSleeptime())
			streamthread = threading.Thread(target=self._stream.serve_forever)
			streamthread.daemon = True
			streamthread.start()
			self.log("Streaming started on " + str(self._stream.server_address))
			self._streaming = True
		except IOError as ioerr:
			self.log(["Error initializing streaming function:", ioerr])
			self._streaming = False

	#Method: setOnStreaming
	def setOnStreaming(self):
		if not self.isStreaming():
			self._setStreaming()
		else:
			self.log("Streaming function is already enabled")

	#Method: setOffStreaming
	def setOffStreaming(self):
		if self.isStreaming():
			try:
				self._stream.shutdown()
				self._stream.server_close()
				self._stream = None
				self._streaming = False
			except IOError as ioerr:
				self.log(["Error disabling streaming function:", ioerr])
		else:
			self.log("Streaming function is not enabled")

	#Method: isStreaming
	def isStreaming(self):
		return self._streaming

	#Method: setStreamingPort
	def setStreamingPort(self, port):
		self._s_port = port

	#Method: getStreamingPort
	def getStreamingPort(self):
		return self._s_port

	#Method: setOnCamera
	def setResolution(self, resolution):
		if self._camera is not None and resolution is not None:
			try:
				self._lock = True
				# Wait 1 second for the usecase when the resolution is set in the same time with the camera start
				time.sleep(1)
				# Set value
				self._resolution = (int(resolution.split(',')[0].strip()), int(resolution.split(',')[1].strip()))
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.resolution = self._resolution
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
				self._lock = False
			except BaseException as baseerr:
				self.log(["Error setting camera resolution:", baseerr])

	#Method: setFramerate
	def setFramerate(self, framerate):
		if self._camera is not None and framerate is not None:
			try:
				self._lock = True
				# Set value
				self._framerate = int(framerate)
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.framerate = self._framerate
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Error setting camera framerate:", baseerr])

	#Method: runStreaming
	def runStreaming(self):
		if self.isStreaming():
			try:
				if self._stream is not None:
					self._stream.setFrame(self.getFrame())
			except IOError as ioerr:
				self.log(["Error streaming data:", ioerr])

	#Method: setSleeptime
	def setSleeptime(self, sleeptime):
		self._s_sleeptime = sleeptime
		if self._stream is not None:
			self._stream.setTimesleep(sleeptime)

	#Method: getSleeptime
	def getSleeptime(self):
		return self._s_sleeptime

	#Method: setRecordingLocation
	def setRecordingLocation(self, location):
		self._r_location = location

	#Method: getRecordingLocation
	def getRecordingLocation(self):
		return self._r_location

	#Method: setRecordingThreshold
	def setRecordingThreshold(self, threshold):
		self._r_threshold = threshold

	#Method: getRecordingThreshold
	def getRecordingThreshold(self):
		return self._r_threshold

	#Method: stop
	def stop(self):
		self._exec = False
		# Stop recording
		if self.isRecording():
			self.setOffRecording()
		# Stop streaming
		if self.isStreaming():
			self.setOffStreaming()
		# Stop camera
		self.setOffCamera()
		# Stop this thread
		self._stop.set()
		self.log("Service has been stopped")

	#Method: stopped
	def stopped(self):
		return self._stop.isSet()

	#Method: log
	def log(self, data):
		if data is not None:
			if isinstance(data, list):
				message = ''
				for obj in data:
					if isinstance(obj, BaseException):
						part = str(obj)
						if part is None or part.strip() == '':
							part = type(obj).__name__
						message += ' ' + part
						if __verbose__:
							traceback.print_exc()
					else:
						message += ' ' + str(obj)
				message = message.strip()
			else:
				message = str(data)
			print "%s | %s > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), self.name, message)

	#Method: start
	def run(self):
		self._exec = True
		# Run surveillance workflow
		while self._exec:
			try:
				# Capture next frame
				self.setFrame()
				# If motion recording feature is active identify motion and save pictures
				self.runRecording()
				# If the streaming is active send the picture through the streaming channel
				self.runStreaming()
				# Sleep for couple of seconds or milliseconds
				time.sleep( self.getSleeptime() )
			except BaseException as baserr:
				self.log(["Service error:", baserr])
				self.stop()

#Class: Motion
class Motion:

	#Constructor
	def __init__(self, camera):
		# Set input parameters
		self._camera = camera
		# Initialize engine parameters
		self._frame_diff = None
		self._frame_gray = None
		self._frame_avrg = None
		self._frame_temp = None

	#Method: isRecording
	def isRecording(self):
		return self._camera.isRecording()

	#Method: getThreshold
	def getThreshold(self):
		return self._camera.getRecordingThreshold()

	#Method: getLocation
	def getLocation(self):
		return self._camera.getRecordingLocation()

	#Method: detect
	def detect(self):
		# Get camera current frame
		frame = self._camera.getFrame()
		if frame is not None:
			# Smooth to get rid of false positives
			cv.Smooth(frame, frame, cv.CV_GAUSSIAN, 3, 0)
			# Check if is needed to initialize the engine
			if self._frame_avrg is None:
				self._frame_diff = cv.CloneImage(frame)
				self._frame_temp = cv.CloneImage(frame)
				self._frame_gray = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_8U, 1)
				self._frame_avrg = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_32F, 3)
				cv.ConvertScale(frame, self._frame_avrg, 1.0, 0.0)
				# Save initial image
				if self.isRecording():
					clone = cv.CloneImage(frame)
					try:
						cv.PutText(clone, "Start monitoring @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime()) ,(10, cv.GetSize(clone)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .3, .3, 0.0, 1, cv.CV_AA ), (255, 255, 255))
						cv.SaveImage(self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".png", clone)
					except IOError as ioerr:
						self._camera.log(["Error saving recording data:", ioerr])
						self._camera._recording = False
			else:
				cv.RunningAvg(frame, self._frame_avrg, 0.020, None)
			# Convert the scale of the moving average.
			cv.ConvertScale(self._frame_avrg, self._frame_temp, 1.0, 0.0)
			# Minus the current frame from the moving average.
			cv.AbsDiff(frame, self._frame_temp, self._frame_diff)
			# Convert the image to grayscale.
			cv.CvtColor(self._frame_diff, self._frame_gray, cv.CV_RGB2GRAY)
			# Convert the image to black and white.
			cv.Threshold(self._frame_gray, self._frame_gray, 70, 255, cv.CV_THRESH_BINARY)
			# Dilate and erode to get people blobs
			cv.Dilate(self._frame_gray, self._frame_gray, None, 18)
			cv.Erode(self._frame_gray, self._frame_gray, None, 10)
			# Get contours
			storage = cv.CreateMemStorage(0)
			contour = cv.FindContours(self._frame_gray, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
			# Evaluate contours
			points = []
			movementArea = 0
			while contour:
				bound_rect = cv.BoundingRect(list(contour))
				contour = contour.h_next()
				# Compute the bounding points to the boxes that will be drawn on the screen
				pt1 = (bound_rect[0], bound_rect[1])
				pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])
				# Add this latest bounding box to the overall area that is being detected as movement
				movementArea += ((pt2[0] - pt1[0]) * (pt2[1] - pt1[1]))
				points.append(pt1)
				points.append(pt2)
				# Draw the contours
				cv.Rectangle(frame, pt1, pt2, cv.CV_RGB(255, 0, 0), 1)
			# Check if it's about movement and save the frame
			if self.isRecording() and movementArea > self.getThreshold():
				clone = cv.CloneImage(frame)
				try:
					cv.PutText(clone, "Motion detected @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime()),(10, cv.GetSize(clone)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .3, .3, 0.0, 1, cv.CV_AA ), (255, 255, 255))
					cv.SaveImage(self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + str(movementArea) + ".png", clone)
				except IOError as ioerr:
					self._camera.log(["Error saving recording data:", ioerr])
					self._camera._recording = False


#Class: PiCamServerHandler
class PiCamServerHandler(BaseRequestHandler):

	#Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseRequestHandler.__init__(self, request, client_address, server)

	#Method: handle
	def handle(self):
		# Get client connection
		self.log("Connection from: " +str(self.client_address))
		# Receive data from client and process it
		command = self.request.recv(1024).strip()
		# Process client requests
		try:
			# Instantiate client structure to detect the action and subject
			self.log("Receiving command: " + str(command))
			data = StateData(command)
			# Action and subject evaluation
			if data.action == 'stop' and data.subject == 'server':
				self.runStopServer()
			if data.action == 'start' and data.subject == 'service':
				self.runStartService(data.target)
			if data.action == 'stop' and data.subject == 'service':
				self.runStopService(data.target)
			if (data.action == 'set' or data.action == 'enable' or data.action == 'disable') and data.subject == 'property':
				self.runSetProperty(data)
			# Send the sign for end of communication
			self.request.sendall(".")
		except BaseException as stderr:
			self.log(["Application error:", stderr])
			if __verbose__:
				traceback.print_exc()

	#Method: log
	def log(self, data, toClient=False):
		if data is not None:
			if isinstance(data, list):
				message = ''
				for obj in data:
					if isinstance(obj, BaseException):
						part = str(obj)
						if part is None or part.strip() == '':
							part = type(obj).__name__
						message += ' ' + part
						if __verbose__:
							traceback.print_exc()
					else:
						message += ' ' + str(obj)
				message = message.strip()
			else:
				message = str(data)
			# Send message to the standard output
			if toClient:
				self.request.sendall(message)
			else:
				print "%s | Server > %s" %(time.strftime("%y%m%d%H%M%S", time.localtime()), message)

	#Method: runStartService
	def runStartService(self, target):
		if target is not None:
			if target in self._server.getCameras():
				self.log("Camera " + target + " is already started", toClient=True)
			else:
				if target is not None:
					camera = Camera(target)
					camera.setStreamingPort(self._server.server_address[1] + 1 + camera.getId())
					camera.start()
					self._server.getCameras()[target] = camera
					self.log("Camera " + target + " has been started", toClient=True)
				else:
					self.log("Camera identifier could not be detected", toClient=True)
		else:
			self.log("Camera identifier was not specified", toClient=True)

	#Method: runStopService
	def runStopService(self, target):
		if target is not None:
			if target in self._server.getCameras():
				camera = self._server.getCameras()[target]
				camera.stop()
				del self._server.getCameras()[target]
				self.log("Camera " + target + " has been stopped", toClient=True)
			else:
				self.log("Camera " + target + " was not yet started", toClient=True)
		else:
			self.log("Camera could not be identified to stop service", toClient=True)

	#Method: runStopServer
	def runStopServer(self):
		self.log("Server shutting down")
		# Stop camera's threads
		if self._server.getCameras():
			keys = self._server.getCameras().keys()
			for key in keys:
				try:
					self.runStopService(key)
					time.sleep(1)
				except BaseException as baserr:
					self.log(["Error stopping service on camera", key , ":", baserr])
		# Stop server thread
		self._server.shutdown()
		self._server.server_close()


	#Method: runSetProperty
	def runSetProperty(self, data):
		# Translate enable and disable actions
		if data.action == data.getActions()[3]:
			data.property += " = True"
		if data.action == data.getActions()[4]:
			data.property += " = False"
		# Ge target camera
		if data.target in self._server.getCameras():
			# Translate property expression
			self.log("Setting '" + data.property + "' on camera " + data.target, toClient=True)
			# Identity target camera
			camera = self._server.getCameras()[data.target]
			# Identify property name and property value
			camprop = data.property.split('=')[0].strip()
			camdata = data.property.split('=')[1].strip()
			# Evaluate streaming property
			if camprop == data.getProperties()[0]:
				if str2bool(camdata):
					camera.setOnStreaming()
				else:
					camera.setOffStreaming()
			# Evaluate recording property
			elif camprop == data.getProperties()[1]:
				if str2bool(camdata):
					camera.setOnRecording()
				else:
					camera.setOffRecording()
			# Evaluate resolution property
			elif camprop == data.getProperties()[2]:
				camera.setResolution(camdata)
			# Evaluate threshold property
			elif camprop == data.getProperties()[3]:
				camera.setRecordingThreshold(int(camdata))
			# Evaluate location property
			elif camprop == data.getProperties()[4]:
				camera.setRecordingLocation(str(camdata))
			# Evaluate sleeptime property
			elif camprop == data.getProperties()[5]:
				camera.setSleeptime(float(camdata))
			# Evaluate framerate property
			elif camprop == data.getProperties()[6]:
				camera.setFramerate(camdata)
		else:
			self.log("Camera " + data.target + " is not yet started", toClient=True)


#Class: PiCamServer
class PiCamServer(ThreadingMixIn, TCPServer):
	#Global variables
	allow_reuse_address = True
	daemon_threads = True
	_cameras = {}

	#Constructor
	def __init__(self, server_address, handler, bind_and_activate=True):
		TCPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._running = True

	#Method: getServerAddress
	def getServerAddress(self):
		return self.server_address

	#Method: getCameras
	def getCameras(self):
		return self._cameras

	#Method: isRunning
	def isRunning(self):
		return self._running

	#Method: shutdown
	def shutdown(self):
		self._running = False
		TCPServer.shutdown(self)

#Class: StreamHandler
class StreamHandler(BaseHTTPRequestHandler):

	#Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseHTTPRequestHandler.__init__(self, request, client_address, server)

	#Method: do_GET
	def do_GET(self):
		try:
			self.send_response(200)
			self.send_header("Connection", "close")
			self.send_header("Max-Age", "0")
			self.send_header("Expires", "0")
			self.send_header("Cache-Control", "no-cache, private")
			self.send_header("Pragma", "no-cache")
			self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--BOUNDARYSTRING")
			self.end_headers()
			while True:
				if self._server.getFrame() is None:
					continue
				JpegData = cv.EncodeImage(".jpeg", self._server.getFrame(), (cv.CV_IMWRITE_JPEG_QUALITY,75)).tostring()
				self.wfile.write("--BOUNDARYSTRING\r\n")
				self.send_header("Content-type", "image/jpeg")
				self.send_header("Content-Length", str(len(JpegData)))
				self.end_headers()
				self.wfile.write(JpegData)
				self.wfile.write("\r\n")
				time.sleep(self._server.getTimesleep())
			return
		except BaseException as baseerr:
			self.send_error(500,'PiCam Streaming Server Error: \r\n\r\n%s' % str(baseerr))
			if __verbose__:
				traceback.print_exc()


#Class: StreamServer
class StreamServer(ThreadingMixIn, HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

	#Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleeptime=0.05):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleeptime = sleeptime

	#Method: getFrame
	def getFrame(self):
		return self._frame

	#Method: getFrame
	def setFrame(self, frame):
		self._frame = frame

	#Method: getTimesleep
	def getTimesleep(self):
		return self._sleeptime

	#Method: setTimesleep
	def setTimesleep(self, sleeptime):
		self._sleeptime = sleeptime


#Class: PiCamClient
class PiCamClient:

	#Constructor
	def __init__(self, host='127.0.0.1', port=9079):
		# Set server host name and port
		self._host = host
		self._port = port
		# Validate host name
		if self._host is None or self._host == '':
			self._host = '127.0.0.1'
		# Validate port
		if self._port is None or not isinstance(self._port, int) or self._port <= 0:
			self._port = 9079
		self._onlog = True

	#Method: getServerAddress
	def getServerAddress(self):
		return self._host + ":" + str(self._port)

	#Method: connect
	def run(self, command):
		# Declare server thread in case of the command will start it
		server = None
		# Instantiate Data module and parse (validate) input command
		try:
			data = StateData(command)
		except BaseException as baserr:
			self.log(["Data error:", baserr])
			sys.exit(1)
		# Check if input command ask to start server instance
		if data.action == "start" and data.subject == "server":
			self.log("Starting PiCam Server instance")
			server = PiCamServer((self._host, self._port), PiCamServerHandler)
			serverhread = threading.Thread(target = server.serve_forever)
			serverhread.daemon = True
			serverhread.start()
			# Check if the current command is linked by other to execute the whole chain
			if data.hasLinkedData():
				data = data.getLinkedData()
				self._onlog = False
			else:
				data = None
		# Check if input comment ask to execute a server command
		while data is not None:
			try:
				# Send command to server instance
				self.log("PiCam Client is calling " + self.getServerAddress())
				client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				client.connect((self._host, self._port))
				# Generate command received from standard input
				command = data.getStatement()
				self.log("Sending command: " + command)
				client.sendall(command)
				# Getting the answer from server
				while True:
					answer = client.recv(1024)
					if answer != '.' and answer != '':
						self.log(answer, True)
						if answer.endswith('.'):
							break
					else:
						break
				client.close()
			except BaseException as baserr:
				self.log(["Client error:", baserr])
			finally:
				#check if the current command is linked by other command
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
		# If server has been instantiated in this process wait to finish his execution
		if server is not None:
			self._onlog = True
			while server.isRunning():
				try:
					time.sleep(1)
				except KeyboardInterrupt:
					print
					self.log('Interrupting server execution by user control')
					# Unlock server socket
					try:
						_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						_socket.connect(("localhost", self._port))
						_socket.sendall("stop server")
						_socket.close()
					except:
						# Nothing to do here
						self.log("Failed running silent shutdown")
		# End program execution
		print "End execution of PiCam.\n"

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
						if __verbose__:
							traceback.print_exc()
					else:
						message += ' ' + str(obj)
				message = message.strip()
			else:
				message = str(data)
			if not server:
				print "%s | Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), message)
			else:
				if self._onlog:
					print "%s | Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), message)


#Class: CmdData
class StateData:
	_actions = ['start', 'stop', 'set', 'enable', 'disable']
	_subjects = ['server', 'service', 'property']
	_properties = ['streaming', 'recording', 'resolution', 'threshold', 'location', 'sleeptime', 'framerate']
	_targetarticles = ['@', 'at', 'on', 'in', 'to']

	#Constructor
	def __init__(self, statement):
		self.action = None
		self.subject = None
		self.location = None
		self.property = None
		self.target = None
		# Validate input command and parse it
		if statement is not None and statement != '':
			if ' and ' in statement:
				self._parse(statement[0:statement.index(' and ')].split(' '))
				self._link = StateData(statement[statement.index(' and ') + 5:])
			else:
				self._parse(statement.split(' '))
				self._link = None
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
					useprep = list(set(self._targetarticles) & set(data))
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
			elif data[0].strip() in self._targetarticles:
				del data[0]
				self.target = '#' + filter(str.isdigit, data[0].strip())
				del data[0]
				self._parse(data)
			else:
				raise RuntimeError("Invalid command part: " + data[0].strip())

	#Method: getTextCommand
	def getStatement(self):
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

	#Method: hasLinkedData
	def hasLinkedData(self):
		return self._link != None

	#Method: getNextData
	def getLinkedData(self):
		return self._link

	#Method: getActions
	def getActions(self):
		return self._actions

	#Method: getSujects
	def getSujects(self):
		return self._subjects

	#Method: getProperties
	def getProperties(self):
		return self._properties

	#Method: getArticles
	def getArticles(self):
		return self._targetarticles


def usage():
	print """
Usage: picam -c "start server" [-f ./picam.cfg] -h "localhost" -p 9079

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
	> picam "start server and start service on #0 and enable property streaming on #0 and enable property recording on #0"
= this is a composed command (by 'and' operator) which can start the server, camera #0 and other. This kind of composed command could be run directly when you start the server or you can executed from client
	> picam -f /opt/clue/etc/picam.cfg
= run picam application using a configuration file (a file with commands), able to start the server or to run specific client actions
	"""

def str2bool(v):
	if v.lower() in ("on", "yes", "true", "t", "1"):
		return True
	elif v.lower() in ("off", "no", "false", "f", "0"):
		return False
	else:
		return None


if __name__=="__main__":
	# Global variables to identify input parameters
	command = None
	file = None
	host = None
	port = None
	# Parse input parameters
	opts, args = getopt.getopt(sys.argv[1:], "c:f:h:p", ["command=", "file=", "host=", "port=", "help"])
	# Collect input parameters
	for opt, arg in opts:
		if opt in ("-c", "--command"):
			command = arg
		elif opt in ("-f", "--file"):
			file = arg
		elif opt in ("-h", "--host"):
			host = arg
		elif opt in ("-p", "--port"):
			port = arg
		elif opt == '--help':
			usage()
			sys.exit(0)
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if (command is None or command == '') and file is None and host is None and port is None:
		command = ' '.join(sys.argv[1:])
	# Check if a configuration file has been specified read it ang get all commands defined in
	if file is not None and os.path.isfile(file):
		cfgfile = open(file, 'r')
		cfglines = cfgfile.readlines()
		cfgfile.close()
		for cmdline in cfglines:
			if cmdline.strip() != '' and not cmdline.strip().startswith('#'):
				if command is not None:
					command += ' and ' + cmdline.strip()
				else:
					command = cmdline.strip()
	# Instantiate Client module an run the command
	client = PiCamClient(host, port)
	client.run(command)
	# Client normal exist
	sys.exit(0)