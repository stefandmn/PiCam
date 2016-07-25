#!/usr/bin/python

__project__ = "Clue"
__module__ = "PiCam"
__author__ = "SDA"
__email__ = "damian.stefan@gmail.com"
__copyright__ = "Copyright (c) 2015-2016, AMSD"
__license__ = "GPL"
__version__ = "1.2.3"
__verbose__ = False

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
				self._resolution = (int(resolution.split(',')[0].strip()), int(resolution.split(',')[1].strip()))
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

	# Method: setMotionRecordingThreshold
	def setMotionRecordingThreshold(self, threshold):
		if self.isMotionDetectionEnabled():
			self._motion.setThreshold(threshold)
		else:
			self.log("Motion detection function will be activated to set recording threshold")
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

	# Method: getMotionRecordingThreshold
	def getMotionRecordingThreshold(self):
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
		self._recording = True
		self._threshold = 1000
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
			if self.isContour():
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
					answer = self.server.runActionServerEcho()
				elif data.action == 'status':
					answer = self.server.runActionServerStatus()
				elif data.action == 'shutdown':
					answer = None
					if self.server.getCameras():
						keys = self.server.getCameras().keys()
						for key in keys:
							subanswer = self.server.runActionStopCamera(key)
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
					answer = self.server.runActionStartCamera(data.target)
				elif data.action == 'stop' and data.subject == 'service':
					answer = self.server.runActionStopCamera(data.target)
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
				answer = self.server.runActionSetProperty(data.target, camprop, camdata)
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
	def runActionServerEcho(self):
		data = '{"action":"echo", "achieved":true, "result":{"project":"' + __project__ + '", "module":"' + __module__ + '"'
		data += ', "version":"' + __version__ + '", "license":"' + __license__ + '", "copyright":"' + __copyright__ + '"}}'
		return data

	# Method: runActionStatus
	def runActionServerStatus(self):
		data = '{"action":"status", "achieved":true, "result":'
		data += '{"project":"' + __project__ + '", "module":"' + __module__ + '", "version":"' + __version__ + '"'
		data += ', "server":"' + str(self.server_address[0]) + '", "port":' + str(self.server_address[1]) + ', "services":'
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
				data += '"CameraId":' + str(camera.getId())
				data += ', "CameraResolution":"' + ('default' if camera.getCameraResolution() is None else str(camera.getCameraResolution()[0]) + 'x' + str(camera.getCameraResolution()[1])) + '"'
				data += ', "CameraFramerate": ' + any2str(camera.getCameraFramerate())
				data += ', "CameraSleeptime": ' + any2str(camera.getCameraSleeptime())
				data += ', "CameraStreaming":' + ('true' if camera.isStreamingEnabled() else "false")
				data += ', "StreamingPort":' + any2str(camera.getStreamingPort())
				data += ', "StreamingSleeptime":' + any2str(camera.getStreamingSleep())
				data += ', "CameraMotionDetection":' + ('true' if camera.isMotionDetectionEnabled() else 'false')
				if camera.isMotionDetectionEnabled():
					data += ', "MotionDetectionContour":' + ('true' if camera.getMotionDetectionContour() else 'false')
					data += ', "MotionDetectionRecording":' + ('true' if camera.getMotionDetectionRecording() else 'false')
					data += ', "MotionRecordingFormat":"' + any2str(camera.getMotionRecordingFormat()) + '"'
					data += ', "MotionRecordingLocation":"' + any2str(camera.getMotionRecordingLocation()) + '"'
					data += ', "MotionRecordingThreshold":' + any2str(camera.getMotionRecordingThreshold())
				data += '}'
				index += 1
			data += ']'
		else:
			data += '[]'
		data += '}}'
		return data

	# Method: runActionStartCamera
	def runActionStartCamera(self, id):
		achieved = False
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = id
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
		data = '{"action":"start", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '"'
		if key is not None:
			data += ', "result":{"service":" camera ' + key + '"}}'
		else:
			data += '}'
		return data

	# Method: runActionStopCamera
	def runActionStopCamera(self, id):
		achieved = False
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = id
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
		data = '{"action":"stop", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '"'
		if key is not None:
			data += ', "result":{"service":"' + key + '"}}'
		else:
			data += '}'
		return data

	# Method: runActionSetProperty
	def runActionSetProperty(self, id, camprop, camdata):
		achieved = True
		msg = ''
		if id is not None:
			if isinstance(id, int):
				key = '#' + str(id)
			else:
				key = id
			# Ge target camera
			if key in self.getCameras():
				try:
					# Identity target camera
					camera = self.getCameras()[key]
					# Evaluate CameraStreaming property
					if camprop.lower() == 'CameraStreaming'.lower():
						if str2bool(camdata):
							camera.setStreamingOn()
						else:
							camera.setStreamingOff()
					# Evaluate CameraMotionDetection property
					elif camprop.lower() == 'CameraMotionDetection'.lower():
						if str2bool(camdata):
							camera.setMotionOn()
						else:
							camera.setMotionOff()
					# Evaluate CameraResolution property
					elif camprop.lower() == 'CameraResolution'.lower():
						camera.setCameraResolution(str(camdata))
					# Evaluate CameraFramerate property
					elif camprop.lower() == 'CameraFramerate'.lower():
						camera.setCameraFramerate(int(camdata))
					# Evaluate CameraSleeptime property
					elif camprop.lower() == 'CameraSleeptime'.lower():
						camera.setCameraSleeptime(float(camdata))
					# Evaluate MotionDetectionContour property
					elif camprop.lower() == 'MotionDetectionContour'.lower():
						camera.setMotionDetectionContour(str2bool(camdata))
					# Evaluate MotionDetectionRecording property
					elif camprop.lower() == 'MotionDetectionRecording'.lower():
						camera.setMotionDetectionRecording(str2bool(camdata))
					# Evaluate MotionRecordingFormat property
					elif camprop.lower() == 'MotionRecordingFormat'.lower():
						camera.setMotionRecordingFormat(str(camdata))
					# Evaluate MotionRecordingThreshold property
					elif camprop.lower() == 'MotionRecordingThreshold'.lower():
						camera.setMotionRecordingThreshold(int(camdata))
					# Evaluate MotionRecordingLocation property
					elif camprop.lower() == 'MotionRecordingLocation'.lower():
						camera.setMotionRecordingLocation(str(camdata))
					# Evaluate StreamingPort property
					elif camprop.lower() == 'StreamingPort'.lower():
						camera.setStreamingPort(int(camdata))
					# Evaluate StreamingSleeptime property
					elif camprop.lower() == 'StreamingSleeptime'.lower():
						camera.setStreamingSleep(float(camdata))
					else:
						achieved = False
						msg = 'Unknown property: ' + camprop
					if achieved:
						msg = "Camera " + key + " has been updated based on property '" + camprop + "' = '" + camdata + "'"
				except BaseException as stderr:
					achieved = False
					msg = tomsg(["Error setting property '" + camprop + "' = '" + camdata + "' on camera " + key + ":", stderr])[1]
			else:
				achieved = False
				msg = "Camera " + key + " is not yet started"
		else:
			key = None
			achieved = False
			msg = "Camera could not be identified to set property"
		data = '{"action":"property", "achieved":' + str(achieved).lower() + ', "message":"' + msg + '"'
		if key is not None:
			data += ', "result":{"service":"' + key + '", "property":"' + camprop + '", "value":"' + camdata + '"}}'
		else:
			data += '}'
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
								self.log(self.echo(jsonanswer), type="INFO", server=True)
							elif jsonanswer["action"] == "status":
								self.log(self.status(jsonanswer), type="INFO", server=True)
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
	def echo(self, answer):
		if answer is not None and answer["result"] is not None:
			return answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"] + ", " + answer["result"]["copyright"]
		else:
			return ""

	# Method: status
	def status(self, answer):
		if answer is not None and answer["result"] is not None:
			text = "Status of " + answer["result"]["project"] + " " + answer["result"]["module"] + " " + answer["result"]["version"]
			text += '\n\t> server: ' + answer["result"]["server"] + ":" + any2str(answer["result"]["port"])
			for service in answer["result"]["services"]:
				text += '\n\t> service: #' + any2str(service["CameraId"])
				if service["CameraStreaming"]:
					text += '\n\t\t| CameraStreaming: On'
					text += '\n\t\t\t|| StreamingPort: ' + any2str(service["StreamingPort"])
					text += '\n\t\t\t|| StreamingSleeptime: ' + any2str(service["StreamingSleeptime"])
				else:
					text += '\n\t\t| CameraStreaming: Off'
				if service["CameraMotionDetection"]:
					text += '\n\t\t| CameraMotionDetection: On'
					if service["MotionDetectionRecording"]:
						text += '\n\t\t\t| MotionDetectionRecording: On'
						text += '\n\t\t\t\t|| MotionRecordingFormat: ' + any2str(service["MotionRecordingFormat"])
						text += '\n\t\t\t\t|| MotionRecordingLocation: ' + any2str(service["MotionRecordingLocation"])
						text += '\n\t\t\t\t|| MotionRecordingThreshold: ' + any2str(service["MotionRecordingThreshold"])
					else:
						text += '\n\t\t\t| MotionDetectionRecording: Off'
					text += '\n\t\t\t| MotionDetectionContour: ' + ('On' if service["MotionDetectionContour"] else 'Off')
				else:
					text += '\n\t\t| CameraMotionDetection: Off'
				text += '\n\t\t|| CameraResolution: ' + ('None' if service["CameraResolution"] is None else any2str(service["CameraResolution"]))
				text += '\n\t\t|| CameraFramerate: ' + any2str(service["CameraFramerate"])
				text += '\n\t\t|| CameraSleeptime: ' + any2str(service["CameraSleeptime"])
			return text
		else:
			return ""


# Class: CmdData
class StateData:
	_actions = ['init', 'shutdown', 'start', 'stop', 'set', 'enable', 'disable', 'status', 'echo']
	_subjects = ['server', 'service', 'property']
	_properties = ['CameraStreaming', 'CameraMotionDetection', 'CameraResolution', 'CameraFramerate', 'CameraSleeptime',
				   'MotionDetectionContour', 'MotionDetectionRecording', 'MotionRecordingFormat', 'MotionRecordingThreshold', 'MotionRecordingLocation',
				   'StreamingPort', 'StreamingSleeptime']
	_targetarticles = ['@', 'at', 'on', 'in', 'to']

	# Constructor
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
		if (self.action == "init" or self.action == "shutdown" or self.action == "status" or self.action == "echo") and not self.subject == "server":
			raise RuntimeError("Invalid subject of init/shutdown/status/echo action: " + any2str(self.subject))
		elif (self.action == "start" or self.action == "stop") and not self.subject == "service":
			raise RuntimeError("Invalid subject of start/stop action: " + any2str(self.subject))
		elif (self.action == "set" or self.action == "enable" or self.action == "disable") and self.subject != "property":
			raise RuntimeError("Invalid action for property action: " + any2str(self.action))
		elif self.subject == 'server' and self.target is not None:
			raise RuntimeError("Invalid subject for the specified target: " + any2str(self.subject))
		elif (self.subject == 'service' or self.subject == 'property') and self.target is None:
			raise RuntimeError("Unknown target for the specified subject: " + any2str(self.subject))
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
				self.target = '#' + filter(str.isdigit, data[0].strip())
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
> picam "init server and start service on #0 and enable property CameraStreaming on #0 and enable property MotionDetectionRecording on #0"
  = this is a composed command (by 'and' operator) which can start the server, camera #0 and others. This kind of composed command could be run directly when you start the server or you can executed from client
> picam -f /opt/clue/etc/picam.cfg
  = run picam application using a configuration file (a file with commands), able to start the server or to run specific client actions
"""


# Function: str2bool
def str2bool(v):
	if v.lower() in ("on", "yes", "true", "t", "1"):
		return True
	elif v.lower() in ("off", "no", "false", "f", "0"):
		return False
	else:
		return None

# Function: str2bool
def any2str(v):
	if v is not None:
		if isinstance(v, bool):
			return str(v).lower()
		else:
			return str(v)
	else:
		return 'null'

# Function: cmdfile
def cmdfile(file, command=''):
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
	return command


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
	file = None
	host = None
	port = None
	# Parse input parameters
	opts, args = getopt.getopt(sys.argv[1:], "c:f:h:i:p:v", ["command=", "file=", "host=", "interface=", "port=", "verbose", "help", "version"])
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
		elif opt == '--help':
			usage()
			sys.exit(0)
		elif opt == '--version':
			print __project__ + " " + __module__ + " " + __version__ + "\n" + __copyright__ + "\n"
			sys.exit(0)
	# Validate command: if command was not specified through input options collect all input parameters and aggregate them in one single command
	if (command is None or command == '') and file is None and host is None and port is None:
		command = ' '.join(sys.argv[1:])
		if command.strip() == 'help':
			usage()
			sys.exit(0)
	# Check if a configuration file has been specified read it ang get all commands defined in
	if file is not None and os.path.isfile(file):
		command = cmdfile(file, command)
	# Instantiate Client module an run the command
	client = PiCamClient(host, port)
	client.run(command)
	# Client normal exist
	sys.exit(0)
