import cv
import cv2
import os
import gc
import sys
import json
import time
import Image
import threading
import traceback
import subprocess
import pprint
import datetime
import numpy

# Function: any2int
def any2int(v):
	if v is not None:
		if isinstance(v, int):
			return v
		else:
			try:
				return int(v)
			except:
				return None
	else:
		return None



# Function: memoryinfo
def memoryinfo():
	try:
		p1 = subprocess.Popen(["cat", "/proc/meminfo"], stdout=subprocess.PIPE)
		p2 = subprocess.Popen(["grep", "Mem"], stdin=p1.stdout, stdout=subprocess.PIPE)
		p1.stdout.close()
		output = p2.communicate()[0]
		data = output.split("\n")[0].split()
		total = any2int(data[1])
		data = output.split("\n")[2].split()
		available = any2int(data[1])
		used = any2int(total) - any2int(available)
		return {"total":any2int(total), "used":used, "available":available}
	except:
		traceback.print_exc()
		return None



print("> Recording ..")

framesno = 0
lastsize = 0
writer = None
recording = True
printerror = True

capture = cv2.VideoCapture(0)
width = capture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
height = capture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)
filename = 'CamCapture.avi'

video = cv2.VideoWriter(filename, cv2.cv.CV_FOURCC('M', 'P', '4', '2'), 8, (int(width), int(height)), True)
start = datetime.datetime.now()
now = datetime.datetime.now()

while recording:
	try:
		retval,image = capture.read()
		
		if not retval:
			break
			
		if framesno % 100 == 0:
			print ("Resources datagram for " + str(framesno) + 
				" frames in " + str(round((datetime.datetime.now() - now).total_seconds(), 2)) + "/" + 
				str(round((datetime.datetime.now() - start).total_seconds(), 2)) + " s: " + json.dumps(memoryinfo()))
			now = datetime.datetime.now()
		
		video.write(image)
		
		if printerror and os.path.isfile(filename):
			if os.path.getsize(filename) == lastsize and lastsize > 0:
				print ("\tNo of frames = " + str(framesno))
				printerror = False
		
		if os.path.isfile(filename):
			lastsize = os.path.getsize(filename)
		framesno += 1
		time.sleep(0.05)
		del image

	except KeyboardInterrupt:
		print ("> Stop recording..")
		recording = False

if video is not None:
	del video
