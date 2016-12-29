#!/usr/bin/python

import __init__

__project__   = __init__.__project__
__module__    = __init__.__module__
__email__     = __init__.__email__
__copyright__ = __init__.__copyright__
__license__   = __init__.__license__
__version__   = __init__.__version__
__verbose__   = False

import os
import io
import cv
import sys
import time
import json
import socket
import getopt
import datetime
import threading
import traceback
from PIL import Image
from picamera import PiCamera
from SocketServer import ThreadingMixIn, BaseRequestHandler, TCPServer
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


# Class: Camera
class Camera(threading.Thread):
	def __init__(self, id, motion=False, streaming=False):
		# Validate camera id input parameter
		if id is not None and str(id).startswith('#'):
			id = int(filter(str.isdigit, id))
		if id is None or not isinstance(id, int) or id < 0:
			raise RuntimeError('Invalid camera identifier: ' + id)
		# Initialize threading options
		threading.Thread.__init__(self)
		self.name = "Camera #" + str(id)
		self._stop = threading.Event()
		# Initialize class public variables (class parameters)
		self._id = id
		self._resolution = (640,480)
		self._framerate = None
		self._sleeptime = 0.05
		# Streaming properties
		self._s_sleep = 0.05
		self._s_port = 9080
		# Initialize class private variables
		self._exec = False
		self._lock = True
		self._frame = None
		# Define tools
		self._camera = None
		self._stream = None
		self._motion = None
		# Identify type of camera and initialize camera device
		self.setCameraOn()
		# Activate recording if was specified during initialization
		if motion:
			self._applyMotion()
		if streaming:
			self._applyStreaming()
		self.log("Service has been initialized")

	# Method: getId
	def getId(self):
		return self._id

	# Method: getFrame
	def getFrame(self):
		return self._frame

	# Method: setFrame
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
			cv.PutText(self._frame, "CAM " + str(self.getId()).rjust(2, '0'), (5, 15), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .35, .35, 0.0, 1, cv.CV_AA), (255, 255, 255))

	# Method: _applyMotion
	def _applyMotion(self):
		self._motion = Motion(self)

	# Method: _runMotionDetection
	def _runMotionDetection(self):
		if self.isMotionDetectionEnabled():
			frame = self.getFrame()
			self._motion.detect(frame)

	# Method: isMotionActive
	def isMotionDetectionEnabled(self):
		return self._motion is not None

	# Method: _setStreaming
	def _applyStreaming(self):
		try:
			self._stream = StreamServer(('0.0.0.0', self._s_port), StreamHandler, frame=self.getFrame(), sleep=self._s_sleep)
			streamthread = threading.Thread(target=self._stream.serve_forever)
			streamthread.daemon = True
			streamthread.start()
			self.log("Streaming started on " + str(self._stream.server_address))
		except IOError as ioerr:
			self.log(["Streaming initialization failed:", ioerr])
			self._stream = None

	# Method: runStreaming
	def _runStreamingBroadcast(self):
		if self.isStreamingEnabled():
			try:
				if self._stream is not None:
					self._stream.setFrame(self.getFrame())
			except IOError as ioerr:
				self.log(["Sending streaming data failed:", ioerr])

	# Method: isStreaming
	def isStreamingEnabled(self):
		return self._stream is not None

	# Method: stop
	def stop(self):
		self._exec = False
		# Stop recording
		if self.isMotionDetectionEnabled():
			self.setMotionOff()
		# Stop streaming
		if self.isStreamingEnabled():
			self.setStreamingOff()
		# Stop camera
		self.setCameraOff()
		# Stop this thread
		self._stop.set()
		self.log("Service has been stopped")

	# Method: stopped
	def stopped(self):
		return self._stop.isSet()

	# Method: log
	def log(self, data):
		type, message = tomsg(data)
		if message != '':
			print "%s | %s %s > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, self.name, message)

	# Method: start
	def run(self):
		self._exec = True
		# Run surveillance workflow
		while self._exec:
			try:
				# Capture next frame
				self.setFrame()
				# If motion recording feature is active identify motion and save pictures
				self._runMotionDetection()
				# If the streaming is active send the picture through the streaming channel
				self._runStreamingBroadcast()
				# Sleep for couple of seconds or milliseconds
				time.sleep(self._sleeptime)
			except BaseException as baserr:
				self.log(["Camera workflow failed:", baserr])
				self.stop()

	# Method: setCameraOn
	def setCameraOn(self):
		if self._camera is None:
			try:
				self._lock = True
				if self._id == 0:
					self._camera = PiCamera()
					if self._resolution is not None:
						self._camera.resolution = self._resolution
					else:
						self._resolution = self._camera.resolution
					if self._framerate is not None:
						self._camera.framerate = self._framerate
					else:
						self._framerate = self._camera.framerate
				else:
					self._camera = cv.CaptureFromCAM(self._id - 1)
					if self._resolution is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
					if self._framerate is not None:
						cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Camera service initialization failed:", baseerr])
		else:
			self.log("Camera service is already started")

	# Method: setCameraOff
	def setCameraOff(self):
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
				self.log(["Camera service has been stopped with errors:", baseerr])
				self._camera = None
		else:
			self.log("Camera service is already stopped")

	# Method: setCameraResolution
	def setCameraResolution(self, resolution):
		if self._camera is not None and resolution is not None:
			try:
				self._lock = True
				# Wait 1 second for the usecase when the resolution is set in the same time with the camera start
				time.sleep(1)
				# Set value
				if resolution.find(",") > 0:
					self._resolution = (int(resolution.split(',')[0].strip()), int(resolution.split(',')[1].strip()))
				elif resolution.lower().find("x") > 0:
					self._resolution = (int(resolution.lower().split('x')[0].strip()), int(resolution.lower().split('x')[1].strip()))
				else:
					raise RuntimeError("Undefined camera resolution value: " + str(resolution))
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.resolution = self._resolution
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_WIDTH, self._resolution[0])
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FRAME_HEIGHT, self._resolution[1])
				self._lock = False
			except BaseException as baseerr:
				self.log(["Applying camera resolution failed:", baseerr])

	# Method: setCameraFramerate
	def setCameraFramerate(self, framerate):
		if self._camera is not None and framerate is not None:
			try:
				self._lock = True
				# Set value
				self._framerate = framerate
				# Configure camera
				if isinstance(self._camera, PiCamera):
					self._camera.framerate = self._framerate
				else:
					cv.SetCaptureProperty(self._camera, cv.CV_CAP_PROP_FPS, self._framerate)
				self._lock = False
			except BaseException as baseerr:
				self.log(["Applying camera framerate failed:", baseerr])

	# Method: setCameraSleeptime
	def setCameraSleeptime(self, sleeptime):
		self._sleeptime = sleeptime

	# Method: setMotionOn
	def setMotionOn(self):
		if not self.isMotionDetectionEnabled():
			self._applyMotion()
		else:
			self.log("Motion detection function is already enabled")

	# Method: setMotionOff
	def setMotionOff(self):
		if self.isMotionDetectionEnabled():
			self._motion = None
		else:
			self.log("Motion detection function is not enabled")

	# Method: setMotionDetectionRecording
	def setMotionDetectionRecording(self, recording):
		if self.isMotionDetectionEnabled():
			self._motion.setRecording(recording)
		else:
			self.log("Motion detection will be activated for recording")
			self.setMotionOn()
			self._motion.setRecording(recording)

	# Method: setMotionRecordingLocation
	def setMotionRecordingLocation(self, location):
		if self.isMotionDetectionEnabled():
			self._motion.setLocation(location)
		else:
			self.log("Motion detection function will be activated to set recording location")
			self.setMotionOn()
			self._motion.setLocation(location)

	# Method: setMotionRecordingFormat
	def setMotionRecordingFormat(self, format):
		if self.isMotionDetectionEnabled():
			self._motion.setFormat(format)
		else:
			self.log("Motion detection function will be activated to set recording format")
			self.setMotionOn()
			self._motion.setFormat(format)

	# Method: setMotionDetectionThreshold
	def setMotionDetectionThreshold(self, threshold):
		if self.isMotionDetectionEnabled():
			self._motion.setThreshold(threshold)
		else:
			self.log("Motion detection function will be activated to set motion threshold")
			self.setMotionOn()
			self._motion.setThreshold(threshold)

	# Method: setMotionDetectionContour
	def setMotionDetectionContour(self, contour):
		if self.isMotionDetectionEnabled():
			self._motion.setContour(contour)
		else:
			self.log("Motion detection function will be activated to set motion contour")
			self.setMotionOn()
			self._motion.setContour(contour)

	# Method: setStreamingOn
	def setStreamingOn(self):
		if not self.isStreamingEnabled():
			self._applyStreaming()
		else:
			self.log("Streaming function is already enabled")

	# Method: setStreamingOff
	def setStreamingOff(self):
		if self.isStreamingEnabled():
			try:
				self._stream.shutdown()
				self._stream.server_close()
				self._stream = None
			except IOError as ioerr:
				self.log(["Streaming function has been stopped with errors:", ioerr])
				self._stream = None
		else:
			self.log("Streaming function is not enabled")

	# Method: setStreamingPort
	def setStreamingPort(self, port):
		self._s_port = port
		if self.isStreamingEnabled():
			self.setStreamingOff()
			self.setStreamingOn()

	# Method: setStreamingSleep
	def setStreamingSleep(self, sleep):
		self._s_sleep = sleep
		if self.isStreamingEnabled():
			self._stream.setSleep(sleep)

	# Method: getCameraResolution
	def getCameraResolution(self):
		return self._resolution

	# Method: getCameraSleeptime
	def getCameraSleeptime(self):
		return self._sleeptime

	# Method: getCameraFramerate
	def getCameraFramerate(self):
		return self._framerate

	# Method: getStreamingPort
	def getStreamingPort(self):
		return self._s_port

	# Method: getStreamingSleep
	def getStreamingSleep(self):
		return self._s_sleep

	# Method: getMotionDetectionRecording
	def getMotionDetectionRecording(self):
		return self._motion.isRecording()

	# Method: getMotionRecordingFormat
	def getMotionRecordingFormat(self):
		return self._motion.getFormat()

	# Method: getMotionRecordingLocation
	def getMotionRecordingLocation(self):
		return self._motion.getLocation()

	# Method: getMotionDetectionThreshold
	def getMotionDetectionThreshold(self):
		return self._motion.getThreshold()

	# Method: getMotionDetectionContour
	def getMotionDetectionContour(self):
		return self._motion.isContour()


# Class: Motion
class Motion:
	# Constructor
	def __init__(self, camera):
		# Set input parameters
		self._camera = camera
		# Initialize engine parameters
		self._gray = None
		self._size = (320,240)
		self._ismot = False
		self._fkmot = 0
		self._avmot = None
		# Motion detection parametrization
		self._format = 'image'
		self._contour = True
		self._recording = False
		self._threshold = 1500
		self._location = '/tmp'

	# Method: isContour
	def isContour(self):
		return self._contour

	# Method: setRecording
	def setContour(self, contour):
		self._contour = contour

	# Method: isRecording
	def isRecording(self):
		return self._recording

	# Method: setRecording
	def setRecording(self, recording):
		self._recording = recording

	# Method: getThreshold
	def getThreshold(self):
		return self._threshold

	# Method: setThreshold
	def setThreshold(self, threshold):
		self._threshold = threshold

	# Method: getLocation
	def getLocation(self):
		return self._location

	# Method: setLocation
	def setLocation(self, location):
		self._location = location

	# Method: getFormat
	def getFormat(self):
		return self._format

	# Method: setFormat
	def setFormat(self, format):
		self._format = format

	# Method: write
	def write(self, frame, text, area=0):
		try:
			clone = cv.CloneImage(frame)
			message = text + " @ " + time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
			cv.PutText(clone, message, (10, cv.GetSize(clone)[1] - 10), cv.InitFont(cv.CV_FONT_HERSHEY_COMPLEX, .32, .32, 0.0, 1, cv.CV_AA), (255, 255, 255))
			if self._format == 'image':
				filename = self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
				if area > 0:
					filename += "-" + str(area) + ".png"
				else:
					filename += ".png"
				cv.SaveImage(filename, clone)
			elif self._format == 'video':
				if not self._ismot:
					if self._avmot is not None:
						del(self._avmot)
						self._avmot = None
					filename = self.getLocation() + os.path.sep + "cam" + str(self._camera.getId()).rjust(2, '0') + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".avi"
					self._avmot = cv.CreateVideoWriter(filename, cv.CV_FOURCC('M', 'J', 'P', 'G'), 2, cv.GetSize(frame), True)
				if self._ismot and self._avmot is not None:
					cv.WriteFrame(self._avmot, clone)
		except IOError as ioerr:
			self._camera.log(["Saving motion data failed:", ioerr])
			self._camera._recording = False

	# Method: gray
	def gray(self, frame):
		copy = cv.CreateImage(cv.GetSize(frame), cv.IPL_DEPTH_8U, 1)
		cv.CvtColor(frame, copy, cv.CV_RGB2GRAY)
		resize = cv.CreateImage(self._size, cv.IPL_DEPTH_8U, 1)
		cv.Resize(copy, resize)
		return resize

	# Method: absdiff
	def absdiff(self, frame1, frame2):
		output = cv.CloneImage(frame1)
		cv.AbsDiff(frame1, frame2, output)
		return output

	# Method: threshold
	def threshold(self, frame):
		cv.Threshold(frame, frame, 35, 255, cv.CV_THRESH_BINARY)
		cv.Dilate(frame, frame, None, 18)
		cv.Erode(frame, frame, None, 10)
		return frame

	# Method: area
	def area(self, move, frame):
		points = []
		area = 0
		xsize = cv.GetSize(frame)[0] / self._size[0]
		ysize = cv.GetSize(frame)[1] / self._size[1]
		storage = cv.CreateMemStorage(0)
		contour = cv.FindContours(move, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
		while contour:
			bound_rect = cv.BoundingRect(list(contour))
			contour = contour.h_next()
			# Compute the bounding points to the boxes that will be drawn on the screen
			pt1 = (bound_rect[0] * xsize, bound_rect[1] * ysize)
			pt2 = ((bound_rect[0] + bound_rect[2]) * xsize, (bound_rect[1] + bound_rect[3]) * ysize)
			# Add this latest bounding box to the overall area that is being detected as movement
			area += ((pt2[0] - pt1[0]) * (pt2[1] - pt1[1]))
			if self.isContour() and area > self.getThreshold():
				points.append(pt1)
				points.append(pt2)
				cv.Rectangle(frame, pt1, pt2, cv.CV_RGB(255,0,0), 1)
		return area

	# Method: detect
	def detect(self, frame):
		if frame is not None:
			# Check if is needed to initialize the engine
			if self._gray is None:
				self.write(frame, "Start monitoring")
				self._gray = self.gray(frame)
			else:
				_gray = self.gray(frame)
				_diff = self.absdiff(self._gray, _gray)
				_move = self.threshold(_diff)
				_area = self.area(_move, frame)
				# Evaluation
				if self.isRecording():
					if _area > self.getThreshold():
						self.write(frame, "Motion detected", _area)
						self._ismot = True
						self._fkmot = 0
					elif self._ismot:
						self._fkmot += 1
						if self._fkmot > 59:
							self._ismot = False
							self._fkmot = 0
				self._gray = _gray


# Class: PiCamServerHandler
class PiCamServerHandler(BaseRequestHandler):
	# Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseRequestHandler.__init__(self, request, client_address, server)

	# Method: handle
	def handle(self):
		# Get client connection
		self.log("Connection from: " + str(self.client_address))
		# Receive data from client and process it
		command = self.request.recv(1024).strip()
		# Process client requests
		try:
			self.log("Receiving client request: " + str(command))
			# Instantiate client structure to detect the action and subject
			data = StateData(command)
			# Evaluate server actions
			if data is not None and data.subject == 'server':
				if data.action == 'echo':
					answer = self.server.runServerEcho()
				elif data.action == 'status':
					answer = self.server.runServerStatus()
				elif data.action == 'load':
					answer = self.server.runServerLoad(data.target)
				elif data.action == 'save':
					answer = self.server.runServerSave(data.target)
				elif data.action == 'shutdown':
					answer = None
					if self.server.getCameras():
						keys = self.server.getCameras().keys()
						for key in keys:
							subanswer = self.server.runServiceStop(key)
							if answer is None:
								jsonanswer = json.loads(subanswer)
								jsonanswer["action"] = "shutdown"
							else:
								jsonmsg = json.loads(subanswer)
								jsonanswer["achieved"] = jsonanswer["achieved"] & jsonmsg["achieved"]
								jsonanswer["message"] += ". " + jsonmsg["message"]
							time.sleep(1)
						answer = '{"action":"shutdown", "achieved":' + str(jsonanswer["achieved"]).lower() + ', "message":"' + jsonanswer["message"] + '"}'
					else:
						answer = '{"action":"shutdown", "achieved":true, "message":"No camera is running"}'
				else:
					raise RuntimeError("Invalid server action: " + any2str(data.action))
			# Evaluate service actions
			elif data is not None and data.subject == 'service':
				if data.action == 'start':
					answer = self.server.runServiceStart(data.target)
				elif data.action == 'stop' and data.subject == 'service':
					answer = self.server.runServiceStop(data.target)
				else:
					raise RuntimeError("Invalid service action: " + any2str(data.action))
			# Evaluate property actions
			elif data is not None and data.subject == 'property':
				if data.action == "enable":
					camprop = data.property.strip()
					camdata = "True"
				elif data.action == "disable":
					camprop = data.property.strip()
					camdata = "False"
				elif data.action == "set":
					camprop = data.property.split('=')[0].strip()
					camdata = data.property.split('=')[1].strip()
				else:
					raise RuntimeError("Invalid property action: " + any2str(data.action))
				answer = self.server.runPropertySet(data.target, camprop, camdata)
			else:
				answer = '{"action":"unknown", "achieved":false, "message":"Command ' + str(data) + ' is not implemented or is unknown"}'
		except BaseException as stderr:
			data = None
			answer = '{"action":"unknown", "achieved":false, "message":"' + tomsg(["Error processing client request:", stderr])[1] + '"}'
		# Send server answer to the client (in JSON format)
		try:
			# If the command is shutdown stop all server threads and deallocate server object
			if data is not None and data.action == 'shutdown' and data.subject == 'server':
				self.server.shutdown()
				self.server = None
			else:
				# Sending answer to client
				self.request.sendall(answer)
		except BaseException as stderr:
			self.log(["Handling server command failed:", stderr])

	# Method: log
	def log(self, data):
		type, message = tomsg(data)
		# Send message to the standard output or to the client console
		if message != '':
			print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)


# Class: PiCamServer
class PiCamServer(ThreadingMixIn, TCPServer):
	# Global variables
	allow_reuse_address = True
	daemon_threads = True
	_cameras = {}

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True):
		TCPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._running = True

	# Method: getCameras
	def getCameras(self):
		return self._cameras

	# Method: isRunning
	def isRunning(self):
		return self._running

	# Method: shutdown
	def shutdown(self):
		self._running = False
		TCPServer.shutdown(self)
		self.server_close()

	# Method: runActionEcho
	def runServerEcho(self):
		data = '{"action":"echo-server", "achieved":true, "result":{"project":"' + __project__ + '", "module":"' + __module__ + '"'
		data += ', "version":"' + __version__ + '", "license":"' + __license__ + '", "copyright":"' + __copyright__ + '"}}'
		return data

	# Method: runActionStatus
	def runServerStatus(self):
		data = '{"action":"status-server", "achieved":true, "result":'
		data += '{"project":"' + __project__ + '", "module":"' + __module__ + '", "version":"' + __version__ + '"'
		data += ', "host":"' + str(self.server_address[0]) + '", "port": ' + str(self.server_address[1]) + ', "services":'
		if self.getCameras():
			data += '['
			index = 0
			keys = self.getCameras().keys()
			for key in keys:
				camera = self.getCameras()[key]
				if index == 0:
					data += '{'
				else:
					data += ', {'
				data += '"CameraId":' + any2str(camera.getId())
				data += ', "CameraStatus":"On"'
				data += ', "CameraResolution":"' + ('default' if camera.getCameraResolution() is None else str(camera.getCameraResolution()[0]) + 'x' + str(camera.getCameraResolution()[1])) + '"'
				data += ', "CameraFramerate":' + ('"default"' if camera.getCameraFramerate() is None else any2str(camera.getCameraFramerate()))
				data += ', "CameraSleeptime":' + any2str(camera.getCameraSleeptime())
				data += ', "CameraStreaming":"' + ('On' if camera.isStreamingEnabled() else 'Off') + '"'
				data += ', "StreamingPort":' + any2str(camera.getStreamingPort())
				data += ', "StreamingSleeptime":' + any2str(camera.getStreamingSleep())
				data += ', "CameraMotionDetection":"' + ('On' if camera.isMotionDetectionEnabled() else 'Off') + '"'
				if camera.isMotionDetectionEnabled():
					data += ', "MotionDetectionContour":"' + ('On' if camera.getMotionDetectionContour() else 'Off') + '"'
					data += ', "MotionDetectionThreshold":' + any2str(camera.getMotionDetectionThreshold())
					data += ', "MotionDetectionRecording":"' + ('On' if camera.getMotionDetectionRecording() else 'Off') + '"'
					data += ', "MotionRecordingFormat":"' + any2str(camera.getMotionRecordingFormat()) + '"'
					data += ', "MotionRecordingLocation":"' + any2str(camera.getMotionRecordingLocation()) + '"'
				data += '}'
				index += 1
			data += ']'
		else:
			data += '[]'
		data += '}}'
		return data

	# Method: runServiceStart
	def runServiceStart(self, id):
		achieved = False
		result = ''
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			if key in self.getCameras():
				msg = "Camera " + key + " is already started"
			else:
				try:
					camera = Camera(key)
					camera.setStreamingPort(self.server_address[1] + 1 + camera.getId())
					camera.start()
					self.getCameras()[key] = camera
					achieved = True
					msg = "Camera " + key + " has been started"
				except BaseException as stderr:
					msg = tomsg(["Error starting camera " + key + ":", stderr])[1]
		else:
			key = None
			msg = "Camera identifier was not specified"
		# Define result key
		if achieved:
			result = '"service":"' + key + '"'
		# Aggregate JSON output
		return '{"action":"start-service", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '", "result":{' + result + '}}'

	# Method: runServiceStop
	def runServiceStop(self, id):
		achieved = False
		result = ''
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			if key in self.getCameras():
				try:
					camera = self.getCameras()[key]
					camera.stop()
					del self.getCameras()[key]
					achieved = True
					msg = "Camera " + key + " has been stopped"
				except BaseException as stderr:
					msg = tomsg(["Error stopping camera " + key + ":", stderr])[1]
			else:
				msg = "Camera " + key + " was not yet started"
		else:
			key = None
			msg = "Camera could not be identified to stop service"
		# Define result key
		if achieved:
			result = '"service":"' + key + '"'
		# Aggregate JSON output
		return '{"action":"stop-service", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '", "result":{' + result + '}}'

	# Method: runPropertySet
	def runPropertySet(self, id, camprop, camdata):
		achieved = True
		result = ''
		msg = ''
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = str(id)
			# Ge target camera
			if key in self.getCameras():
				try:
					# Identity target camera
					camera = self.getCameras()[key]
					# Evaluate CameraStreaming property
					if camprop.lower() == 'CameraStreaming'.lower():
						if any2bool(camdata):
							camera.setStreamingOn()
						else:
							camera.setStreamingOff()
					# Evaluate CameraMotionDetection property
					elif camprop.lower() == 'CameraMotionDetection'.lower():
						if any2bool(camdata):
							camera.setMotionOn()
						else:
							camera.setMotionOff()
					# Evaluate CameraResolution property
					elif camprop.lower() == 'CameraResolution'.lower():
						camera.setCameraResolution(any2str(camdata))
					# Evaluate CameraFramerate property
					elif camprop.lower() == 'CameraFramerate'.lower():
						camera.setCameraFramerate(any2int(camdata))
					# Evaluate CameraSleeptime property
					elif camprop.lower() == 'CameraSleeptime'.lower():
						camera.setCameraSleeptime(any2float(camdata))
					# Evaluate MotionDetectionContour property
					elif camprop.lower() == 'MotionDetectionContour'.lower():
						camera.setMotionDetectionContour(any2bool(camdata))
					# Evaluate MotionDetectionThreshold property
					elif camprop.lower() == 'MotionDetectionThreshold'.lower():
						camera.setMotionDetectionThreshold(any2int(camdata))
					# Evaluate MotionDetectionRecording property
					elif camprop.lower() == 'MotionDetectionRecording'.lower():
						camera.setMotionDetectionRecording(any2bool(camdata))
					# Evaluate MotionRecordingFormat property
					elif camprop.lower() == 'MotionRecordingFormat'.lower():
						camera.setMotionRecordingFormat(any2str(camdata))
					# Evaluate MotionRecordingLocation property
					elif camprop.lower() == 'MotionRecordingLocation'.lower():
						camera.setMotionRecordingLocation(any2str(camdata))
					# Evaluate StreamingPort property
					elif camprop.lower() == 'StreamingPort'.lower():
						camera.setStreamingPort(any2int(camdata))
					# Evaluate StreamingSleeptime property
					elif camprop.lower() == 'StreamingSleeptime'.lower():
						camera.setStreamingSleep(any2float(camdata))
					else:
						achieved = False
						msg = 'Unknown property: ' + camprop
					if achieved:
						msg = "Camera " + key + " has been updated based on property '" + camprop + "' = '" + str(camdata) + "'"
				except BaseException as stderr:
					achieved = False
					msg = tomsg(["Error setting property '" + camprop + "' = '" + str(camdata) + "' on camera " + key + ":", stderr])[1]
			else:
				achieved = False
				msg = "Camera " + key + " is not yet started"
		else:
			key = None
			achieved = False
			msg = "Camera could not be identified to set property"
		# Define result key
		if achieved:
			result='"service":"' + key + '", "property":"' + camprop + '", "value":"' + str(camdata) + '"'
		# Aggregate JSON output
		return '{"action":"set-property", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '", "result":{' + result + '}}'

	# Method: runServerLoad
	def runServerLoad(self, path):
		achieved = True
		result = None
		if path is not None and os.path.isfile(path):
			try:
				# Read the file content
				file = open(path, 'r')
				cfg = json.load(file)
				file.close()
				result = '"file":"' + path + '"'
				msg = "Configuration loaded from target location: " + str(path)
				if cfg.get("services"):
					for service in cfg['services']:
						# Validate camera id and status
						if service.get("CameraId") is None:
							continue
						# Get camera identifier
						CameraId = int(filter(str.isdigit, str(service["CameraId"])))
						CameraStarted = False
						# Check camera status
						if service.get("CameraStatus") and any2bool(service["CameraStatus"]):
							jsonout = json.loads(self.runServiceStart(CameraId))
							CameraStarted = jsonout["achieved"]
							msg += '. ' + str(jsonout["message"])
							result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							if not jsonout["achieved"]:
								continue
						elif service.get("CameraStatus") and not any2bool(service["CameraStatus"]):
							jsonout = json.loads(self.runServiceStop(CameraId))
							msg += '. ' + str(jsonout["message"])
							result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							continue
						# Check camera resolution
						if service.get("CameraResolution") and service["CameraResolution"] != "default":
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraResolution", service["CameraResolution"]))
							msg += '. ' + str(jsonout["message"])
							result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						# Check camera framerate
						if service.get("CameraFramerate") and service["CameraFramerate"] != "default":
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraFramerate", service["CameraFramerate"]))
							msg += '. ' + str(jsonout["message"])
							result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						# Check camera sleeptime
						if service.get("CameraSleeptime") and service["CameraSleeptime"] != "default":
							jsonout = json.loads(self.runPropertySet(CameraId, "CameraSleeptime", service["CameraSleeptime"]))
							msg += '. ' + str(jsonout["message"])
							result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						# Check camera streaming
						if not service.get("CameraStreaming") or (service.get("CameraStreaming") and service["CameraStreaming"] == "default") or (service.get("CameraStreaming") and any2bool(service["CameraStreaming"])):
							if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraStreaming", service["CameraStreaming"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							if service.get("StreamingPort") and service["StreamingPort"] != "default":
								jsonout = json.loads(self.runPropertySet(CameraId, "StreamingPort", service["StreamingPort"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							if service.get("StreamingSleeptime") and service["StreamingSleeptime"] != "default":
								jsonout = json.loads(self.runPropertySet(CameraId, "StreamingSleeptime", service["StreamingSleeptime"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
							if not CameraStarted:
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraStreaming", service["CameraStreaming"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						# Check camera motion detection
						if not service.get("CameraMotionDetection") or (service.get("CameraMotionDetection") and service["CameraMotionDetection"] == "default") or (service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"])):
							if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraMotionDetection", service["CameraMotionDetection"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							if service.get("MotionDetectionContour") and service["MotionDetectionContour"] != "default":
								jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionContour", service["MotionDetectionContour"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							if service.get("MotionDetectionThreshold") and service["MotionDetectionThreshold"] != "default":
								jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionThreshold", service["MotionDetectionThreshold"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							# Check motion detection recording option
							if not service.get("MotionDetectionRecording") or (service.get("MotionDetectionRecording") and service["MotionDetectionRecording"] == "default") or (service.get("MotionDetectionRecording") and any2bool(service["MotionDetectionRecording"])):
								if service.get("MotionDetectionRecording") and any2bool(service["MotionDetectionRecording"]):
									jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionRecording", service["MotionDetectionRecording"]))
									msg += '. ' + str(jsonout["message"])
									result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
								if service.get("MotionRecordingFormat") and service["MotionRecordingFormat"] != "default":
									jsonout = json.loads(self.runPropertySet(CameraId, "MotionRecordingFormat", service["MotionRecordingFormat"]))
									msg += '. ' + str(jsonout["message"])
									result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
								if service.get("MotionRecordingLocation") and service["MotionRecordingLocation"] != "default":
									jsonout = json.loads(self.runPropertySet(CameraId, "MotionRecordingLocation", service["MotionRecordingLocation"]))
									msg += '. ' + str(jsonout["message"])
									result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
							elif service.get("MotionDetectionRecording") and not any2bool(service["MotionDetectionRecording"]):
								if not CameraStarted:
									jsonout = json.loads(self.runPropertySet(CameraId, "MotionDetectionRecording", service["MotionDetectionRecording"]))
									msg += '. ' + str(jsonout["message"])
									result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
						elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
							if not CameraStarted:
								jsonout = json.loads(self.runPropertySet(CameraId, "CameraMotionDetection", service["CameraMotionDetection"]))
								msg += '. ' + str(jsonout["message"])
								result += (', "' + jsonout["action"] + '":' + json.dumps(jsonout["result"])) if jsonout["achieved"] else ''
			except BaseException as stderr:
				result = ''
				achieved = False
				msg = tomsg(["Error loading server configuration from file " + path + ": ", stderr])[1]
		else:
			achieved = False
			msg = "Invalid target location: " + str(path)
		# Aggregate JSON output
		#print "> TEST 0n \n" + '{"action":"load-server", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '", "result":{' + result + '}}'
		return '{"action":"load-server", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '", "result":{' + result + '}}'

	# Method: runServerLoad
	def runServerSave(self, path):
		achieved = True
		if path is not None and os.path.isfile(path):
			try:
				# Read the file content
				file = open(path, 'r')
				cfgdata = json.load(file)
				file.close()

				message = "Configuration saved in target location: " + str(path)
			except BaseException as stderr:
				achieved = False
				msg = tomsg(["Error saving server configuration in file " + path + ": ", stderr])[1]
		else:
			achieved = False
			msg = "Invalid target location: " + str(path)
		data = '{"action":"save-server", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '"}'
		return data


# Class: StreamHandler
class StreamHandler(BaseHTTPRequestHandler):
	# Constructor
	def __init__(self, request, client_address, server):
		self._server = server
		BaseHTTPRequestHandler.__init__(self, request, client_address, server)

	# Method: do_GET
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
				JpegData = cv.EncodeImage(".jpeg", self._server.getFrame(), (cv.CV_IMWRITE_JPEG_QUALITY, 75)).tostring()
				self.wfile.write("--BOUNDARYSTRING\r\n")
				self.send_header("Content-type", "image/jpeg")
				self.send_header("Content-Length", str(len(JpegData)))
				self.end_headers()
				self.wfile.write(JpegData)
				self.wfile.write("\r\n")
				time.sleep(self._server.getSleep())
			return
		except BaseException as baseerr:
			self.send_error(500, 'PiCam Streaming Server Error: \r\n\r\n%s' % str(baseerr))
			if __verbose__:
				traceback.print_exc()


# Class: StreamServer
class StreamServer(ThreadingMixIn, HTTPServer):
	allow_reuse_address = True
	daemon_threads = True

	# Constructor
	def __init__(self, server_address, handler, bind_and_activate=True, frame=None, sleep=0.05):
		HTTPServer.__init__(self, server_address, handler, bind_and_activate=bind_and_activate)
		self._frame = frame
		self._sleep = sleep

	# Method: getFrame
	def getFrame(self):
		return self._frame

	# Method: getFrame
	def setFrame(self, frame):
		self._frame = frame

	# Method: getTimesleep
	def getSleep(self):
		return self._sleep

	# Method: setTimesleep
	def setSleep(self, sleeptime):
		self._sleep = sleeptime


# Class: PiCamClient
class PiCamClient:
	# Constructor
	def __init__(self, host='127.0.0.1', port=9079, api=False):
		# Set server host name and port
		self._host = host
		self._port = port
		# Validate host name
		if self._host is None or self._host == '':
			self._host = '127.0.0.1'
		# Validate port
		if self._port is None or not isinstance(self._port, int) or self._port <= 0:
			self._port = 9079
		self._api = api
		self._apiData = []

	# Method: connect
	def run(self, command):
		# Declare server thread in case of the command will start it
		server = None
		# Instantiate Data module and parse (validate) input command
		try:
			data = StateData(command)
		except BaseException as baserr:
			errordata = ["Command translation failed:", baserr]
			if not self._api:
				self.log(errordata)
				sys.exit(1)
			else:
				self._apiData.append('{"action":"unknown", "achieved":false, "message":' + tomsg(errordata)[1])
				return self._apiData
		# Check if input command ask to start server instance
		if data.action == "init" and data.subject == "server":
			try:
				server = PiCamServer((self._host, self._port), PiCamServerHandler)
				serverhread = threading.Thread(target=server.serve_forever)
				serverhread.daemon = True
				serverhread.start()
				# Write output to std output or write it through API chain
				infodata = __project__ + " " + __module__ + " Server has been initialized"
				if not self._api:
					self.log(infodata)
				else:
					self._apiData.append('{"action":"init", "achieved":true, "message":' + tomsg(infodata)[1])
				# Check if the current command is linked by other to execute the whole chain
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
			except BaseException as baserr:
				errordata = ["PiCam server failed:", baserr]
				self.log(errordata)
				server = None
				data = None
		# Check if input comment ask to execute a server command
		while data is not None:
			try:
				# Send command to server instance
				self.log(__project__ + " " + __module__ + " Client is calling " + self._host + ":" + str(self._port))
				client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				client.connect((self._host, self._port))
				# Generate command received from standard input
				command = data.getStatement()
				self.log("Sending command: " + command)
				client.sendall(command)
				# Getting the answers from server
				while True:
					answer = client.recv(1024)
					if answer is not None and answer != '':
						if not self._api:
							# Get JSON structure
							jsonanswer = json.loads(answer)
							# Read message type and value to be displayed to STD output
							if jsonanswer is not None:
								if jsonanswer.get("message") is not None:
									message = jsonanswer["message"]
								else:
									message = None
								if jsonanswer["achieved"]:
									level = "INFO"
								else:
									level = "ERROR"
							else:
								message = "Server message could not be translated: " + str(answer)
								level = "ERROR"
							# Display message to standard output
							if jsonanswer["action"] == "echo":
								self.log(self._echo(jsonanswer), type="INFO", server=True)
							elif jsonanswer["action"] == "status":
								self.log(self._status(jsonanswer), type="INFO", server=True)
							elif message is not None:
								self.log(message, type=level, server=True)
						else:
							self._apiData.append(answer)
					else:
						break
				client.close()
			except BaseException as baserr:
				errordata = ["Command failed:", baserr]
				if not self._api:
					self.log(errordata)
				else:
					self._apiData.append('{"action":"' + data.action + '", "achieved":false, "message":' + tomsg(errordata)[1])
			finally:
				# Check if the current command is linked by other command
				if data.hasLinkedData():
					data = data.getLinkedData()
				else:
					data = None
		# If server has been instantiated in this process wait to finish his execution
		if server is not None and not self._api:
			while server.isRunning():
				try:
					time.sleep(1)
				except KeyboardInterrupt:
					print
					self.log('Interrupting server execution by user control', type="INFO", server=True)
					# Unlock server socket
					try:
						_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
						_socket.connect(("localhost", self._port))
						_socket.sendall("shutdown server")
						_socket.close()
					except:
						# Nothing to do here
						self.log("Failed running silent shutdown", type="ERROR", server=True)
		# End program execution
		if not self._api:
			print ""
		else:
			if len(self._apiData) == 1:
				return self._apiData[0]
			else:
				return self._apiData

	# Method: log
	def log(self, data, type=None, server=False):
		type, message = tomsg(data, type)
		# Evaluate message and type
		if message != '' and not self._api:
			if not server:
				print "%s | %s Client > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)
			else:
				print "%s | %s Server > %s" % (time.strftime("%y%m%d%H%M%S", time.localtime()), type, message)

	# Method: echo
	def _echo(self, answer):
		if answer is not None and answer["result"] is not None:
			return answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"] + ", " + answer["result"]["copyright"]
		else:
			return ""

	# Method: status
	def _status(self, answer):
		if answer is not None and answer["result"] is not None:
			text = "Status of " + answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"]
			text += '\n\t> server: ' + answer["result"]["host"] + ":" + any2str(answer["result"]["port"])
			for service in answer["result"]["services"]:
				text += '\n\t> Service: #' + any2str(service["CameraId"])
				# Main Properties
				text += '\n\t\t| CameraResolution: ' + ('default' if service["CameraResolution"] is None else any2str(service["CameraResolution"]))
				text += '\n\t\t| CameraFramerate: ' + any2str(service["CameraFramerate"])
				text += '\n\t\t| CameraSleeptime: ' + any2str(service["CameraSleeptime"])
				# Streaming
				if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
					text += '\n\t\t| CameraStreaming: On'
					text += '\n\t\t\t|| StreamingPort: ' + any2str(service["StreamingPort"])
					text += '\n\t\t\t|| StreamingSleeptime: ' + any2str(service["StreamingSleeptime"])
				elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
					text += '\n\t\t| CameraStreaming: Off'
				# Motion Detection
				if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
					text += '\n\t\t| CameraMotionDetection: On'
					text += '\n\t\t\t|| MotionDetectionContour: ' + ('On' if service["MotionDetectionContour"] else 'Off')
					text += '\n\t\t\t|| MotionDetectionThreshold: ' + any2str(service["MotionDetectionThreshold"])
					# Recording
					if service.get("MotionDetectionRecording") and any2bool(service["MotionDetectionRecording"]):
						text += '\n\t\t\t|| MotionDetectionRecording: On'
						text += '\n\t\t\t\t||| MotionRecordingFormat: ' + any2str(service["MotionRecordingFormat"])
						text += '\n\t\t\t\t||| MotionRecordingLocation: ' + any2str(service["MotionRecordingLocation"])
					elif service.get("MotionDetectionRecording") and not any2bool(service["MotionDetectionRecording"]):
						text += '\n\t\t\t|| MotionDetectionRecording: Off'
				elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
					text += '\n\t\t| CameraMotionDetection: Off'
			return text
		else:
			return ""

	# Method: command
	def load(self, filename, command=''):
		if filename is not None and os.path.isfile(filename):
			try:
				# Read the file content
				file = open(filename, 'r')
				content = file.readlines()
				file.close()
				# Check if content if JSON, otherwise  parse and run it
				if '\n'.join(content).strip().startswith('{') and '\n'.join(content).strip().endswith('}'):
					data = json.loads('\n'.join(content).strip())
					content = []
					if data.get("host") and data["host"] != "default":
						self._host = data["host"]
					if data.get("port") and data["port"] != "default":
						self._port = data["port"]
					if data.get('server') and (data['server'] == "init" or data['server'] == "shutdown"):
						content.append("server " + data['server'])
					# Handle services
					if data.get("services"):
						for service in data['services']:
							# Validate camera id
							if service.get("CameraId") is None:
								continue
							# Get camera identifier
							CameraId = " on #" + any2str(service["CameraId"])
							CameraStarted = False
							# Check camera status
							if service.get("CameraStatus") and any2bool(service["CameraStatus"]):
								content.append("start service" + CameraId)
								CameraStarted = True
							elif service.get("CameraStatus") and not any2bool(service["CameraStatus"]):
								if data.get('server') is None or (data.get('server') and data['server'] != "init"):
									content.append("stop service" + CameraId)
								continue
							# Check camera resolution
							if service.get("CameraResolution") and service["CameraResolution"] != "default":
								content.append("set property CameraResolution=" + service["CameraResolution"] + CameraId)
							# Check camera framerate
							if service.get("CameraFramerate") and service["CameraFramerate"] != "default":
								content.append("set property CameraFramerate=" + service["CameraFramerate"] + CameraId)
							# Check camera sleeptime
							if service.get("CameraSleeptime") and service["CameraSleeptime"] != "default":
								content.append("set property CameraSleeptime=" + service["CameraSleeptime"] + CameraId)
							# Check camera streaming
							if not service.get("CameraStreaming") or (service.get("CameraStreaming") and service["CameraStreaming"] == "default") or (service.get("CameraStreaming") and any2bool(service["CameraStreaming"])):
								if service.get("CameraStreaming") and any2bool(service["CameraStreaming"]):
									content.append("enable property CameraStreaming" + CameraId)
								if service.get("StreamingPort") and service["StreamingPort"] != "default":
									content.append("set property StreamingPort=" + service["StreamingPort"] + CameraId)
								if service.get("StreamingSleeptime") and service["StreamingSleeptime"] != "default":
									content.append("set property StreamingSleeptime=" + service["StreamingSleeptime"] + CameraId)
							elif service.get("CameraStreaming") and not any2bool(service["CameraStreaming"]):
								if not CameraStarted:
									content.append("disable property CameraStreaming" + CameraId)
							# Check camera motion detection
							if not service.get("CameraMotionDetection") or (service.get("CameraMotionDetection") and service["CameraMotionDetection"] == "default") or (service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"])):
								if service.get("CameraMotionDetection") and any2bool(service["CameraMotionDetection"]):
									content.append("enable property CameraMotionDetection" + CameraId)
								if service.get("MotionDetectionContour") and service["MotionDetectionContour"] != "default" and any2bool(service["MotionDetectionContour"]):
									content.append("enable property MotionDetectionContour" + CameraId)
								elif service.get("MotionDetectionContour") and service["MotionDetectionContour"] != "default" and not any2bool(service["MotionDetectionContour"]):
									content.append("disable property MotionDetectionContour" + CameraId)
								if service.get("MotionDetectionThreshold") and service["MotionDetectionThreshold"] != "default":
									content.append("set property MotionDetectionThreshold=" + str(service["MotionDetectionThreshold"]) + CameraId)
								# Check motion detection recording option
								if not service.get("MotionDetectionRecording") or (service.get("MotionDetectionRecording") and service["MotionDetectionRecording"] == "default") or (service.get("MotionDetectionRecording") and any2bool(service["MotionDetectionRecording"])):
									if service.get("MotionDetectionRecording") and any2bool(service["MotionDetectionRecording"]):
										content.append("enable property MotionDetectionRecording" + CameraId)
									if service.get("MotionRecordingFormat") and service["MotionRecordingFormat"] != "default":
										content.append("set property MotionRecordingFormat=" + service["MotionRecordingFormat"] + CameraId)
									if service.get("MotionRecordingLocation") and service["MotionRecordingLocation"] != "default":
										content.append("set property MotionRecordingLocation=" + service["MotionRecordingLocation"] + CameraId)
								elif service.get("MotionDetectionRecording") and not any2bool(service["MotionDetectionRecording"]):
									if not CameraStarted:
										content.append("disable property MotionDetectionRecording" + CameraId)
							elif service.get("CameraMotionDetection") and not any2bool(service["CameraMotionDetection"]):
								if not CameraStarted:
									content.append("disable property CameraMotionDetection" + CameraId)
				# Build composed command
				for cmdline in content:
					if cmdline.strip() != '' and not cmdline.strip().startswith('#'):
						if command is not None:
							command += ' and ' + cmdline.strip()
						else:
							command = cmdline.strip()
			except BaseException as baserr:
				self.log(["Error transforming configuration into command:", baserr], type="ERROR", server=False)
		return command


# Class: CmdData
class StateData:
	_actions = ['init', 'shutdown', 'start', 'stop', 'set', 'enable', 'disable', 'status', 'echo', 'load', 'save']
	_subjects = ['server', 'service', 'property']
	_properties = ['CameraStreaming', 'CameraMotionDetection', 'CameraResolution', 'CameraFramerate', 'CameraSleeptime',
				   'MotionDetectionContour', 'MotionDetectionRecording', 'MotionRecordingFormat', 'MotionDetectionThreshold', 'MotionRecordingLocation',
				   'StreamingPort', 'StreamingSleeptime']
	_targetarticles = ['@', 'at', 'on', 'in', 'to', 'from']

	# Constructor
	def __init__(self, statement):
		self.action = None
		self.subject = None
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
		if (self.action == "init" or self.action == "shutdown" or self.action == "status" or self.action == "echo" or self.action == "load" or self.action == "save") and not self.subject == "server":
			raise RuntimeError("Invalid subject of init/shutdown/status/echo/load/save action: " + any2str(self.subject))
		elif (self.action == "start" or self.action == "stop") and not self.subject == "service":
			raise RuntimeError("Invalid subject of start/stop action: " + any2str(self.subject))
		elif (self.action == "set" or self.action == "enable" or self.action == "disable") and self.subject != "property":
			raise RuntimeError("Invalid action for property action: " + any2str(self.action))
		elif self.subject == 'server' and (self.action == "load" or self.action == "save") and self.target is None:
			raise RuntimeError("Unknown target for the specified subject and action: " + any2str(self.subject) + "/" + any2str(self.action))
		elif (self.subject == 'service' or self.subject == 'property') and self.target is None:
			raise RuntimeError("Unknown target for the specified subject and action: " + any2str(self.subject) + "/" + any2str(self.action))
		elif self.action is None or self.action == '':
			raise RuntimeError("Action can not be null")
		elif self.subject is None or self.subject == '':
			raise RuntimeError("Subject can not be null")

	# Method: _parse
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
						self.property = ' '.join(data[0:index]).strip()
						del data[0:index]
					else:
						self.property = ' '.join(data).strip()
						del data[:]
					if not self.property.split('=')[0].strip() in self._properties:
						raise RuntimeError("Invalid property: " + self.property.split('=')[0].strip())
				self._parse(data)
			elif data[0].strip() in self._targetarticles:
				del data[0]
				if data[0].strip()[0] in ['.', '/']:
					self.target = str(data[0].strip())
				else:
					self.target = '#' + filter(str.isdigit, str(data[0].strip()))
				del data[0]
				self._parse(data)
			else:
				raise RuntimeError("Invalid command part: " + data[0].strip())

	# Method: getTextCommand
	def getStatement(self):
		outcmd = None
		if self.action is not None and self.subject is not None:
			outcmd = self.action + " " + self.subject
			if self.subject == self._subjects[2]:
				outcmd += " " + self.property
		if self.target is not None:
			outcmd += " on " + self.target
		return outcmd

	# Method: getTargetId
	def getTargetId(self):
		if self.target is not None:
			return int(filter(str.isdigit, self.target))
		else:
			return None

	# Method: hasLinkedData
	def hasLinkedData(self):
		return self._link != None

	# Method: getNextData
	def getLinkedData(self):
		return self._link

	# Method: getActions
	def getActions(self):
		return self._actions

	# Method: getSujects
	def getSujects(self):
		return self._subjects

	# Method: getProperties
	def getProperties(self):
		return self._properties

	# Method: getArticles
	def getArticles(self):
		return self._targetarticles


# Function: usage
def usage():
	print "\n" + __project__ + " " + __module__ + " " + __version__ + ", " + __license__ + ", " + __copyright__ + """
Usage: picam -c "init server" [-f ./picam.cfg] -i "0.0.0.0" -p 9079

Options:
 -v, --verbose    run in verbosity mode
 -c, --command    describe the command that should be executed by server component
 -i, --interface  host interface to start server component
 -h, --host       host name/ip of the server for client connectivity
 -p, --port       host port number for client connectivity
 -f, --file       file with command to start server instance or to run client commands
 --help           this help text
 --version        version of picam client

Examples:
> picam -c "init server"
> picam --command="init server"
  = run server (using default hostname and port) using input options
> picam init server
  = run server (using default hostname and port) aggregating command from all input parameters
> picam -c "init server" -i "0.0.0.0" -p 6400
> picam --command="init server" --interface="127.0.0.1" --port=6400
  = run server (using default hostname and port) using input options
> picam -c "start service on #1"
> picam --command="start service on c1"
  = run client to start on server camera #1. The client will connect to server using default port
> picam enable recording on c0
  = run client (using default hostname and port) aggregating command from all input parameters
> picam -c "set property CameraResolution=1280,720 on c1" -h "192.168.0.100" -p 6400
> picam --command="set property CameraResolution=1280,720 on c1" --host="127.0.0.1" --port=6400
  = run client that will send the command described by a specific option to a dedicated server
"""


# Function: str2bool
def any2bool(v):
	if isinstance(v, bool):
		return v
	if isinstance(v, int):
		return True if v > 0 else False
	elif v.lower() in ("on", "yes", "true", "t", "1", "enable", "enabled", "active", "start", "started"):
		return True
	elif v.lower() in ("off", "no", "false", "f", "0", "disable", "disabled", "inactive", "stop", "stopped"):
		return False
	else:
		return False

# Function: any2int
def any2int(v):
	if v is not None:
		if isinstance(v, int):
			return v
		else:
			return int(v)
	else:
		return None

# Function: any2float
def any2float(v):
	if v is not None:
		if isinstance(v, float):
			return v
		else:
			return float(v)
	else:
		return None

# Function: any2str
def any2str(v):
	if v is not None:
		if isinstance(v, bool):
			return str(v).lower()
		else:
			return str(v)
	else:
		return None

# Function: log
def tomsg(data, level=None):
	objlist = []
	message = ''
	# Define the list of objects and values
	if data is not None:
		if not isinstance(data, list):
			objlist.append(data)
		else:
			objlist = data
	# Build message
	for obj in objlist:
		if isinstance(obj, BaseException):
			# When verbose is activated print out the stacktrace
			if __verbose__:
				traceback.print_exc()
			# Take exception details to be described in log message
			part = str(obj)
			if part is None or part.strip() == '':
				part = type(obj).__name__
			message += ' ' + part
			level = "ERROR"
		else:
			message += ' ' + str(obj)
	if level is None or level == '': level = "INFO"
	# return turtle
	return level, message.strip()


# Main program
if __name__ == "__main__":
	# Global variables to identify input parameters
	command = None
	apimode = False
	file = None
	host = None
	port = None
	try:
		# Parse input parameters
		opts, args = getopt.getopt(sys.argv[1:], "c:f:h:i:p:v", ["command=", "file=", "host=", "interface=", "port=", "verbose", "help", "version", "api"])
		# Collect input parameters
		for opt, arg in opts:
			if opt in ("-c", "--command"):
				command = arg
			elif opt in ("-f", "--file"):
				file = arg
			elif opt in ("-h", "--host", "-i", "--interface"):
				host = arg
			elif opt in ("-p", "--port"):
				port = arg
			elif opt in ("-v", "--verbose"):
				__verbose__ = True
			elif opt == '--api':
				apimode = True
			elif opt == '--help':
				usage()
				sys.exit(0)
			elif opt == '--version':
				print __project__ + " " + __module__ + " " + __version__ + "\n" + __copyright__ + "\n"
				sys.exit(0)
	except BaseException as baserr:
		command = None
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if (command is None or command == '') and file is None and host is None and port is None:
		command = ' '.join(sys.argv[1:])
		if command.strip() == 'help':
			usage()
			sys.exit(0)
	# Instantiate Client module an then run the command
	client = PiCamClient(host, port, api=apimode)
	# Check if a configuration file has been specified, read it ang get all commands defined in
	if file is not None and os.path.isfile(file):
		command = client.load(file, command)
	# Run identified command
	if not apimode:
		client.run(command)
	elif apimode:
		cmdout = client.run(command)
		print cmdout
	# Client normal exist
	sys.exit(0)
