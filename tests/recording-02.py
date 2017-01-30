import cv
import os
import gc
import sys
import json
import time
import numpy
import threading
import traceback
import subprocess
import datetime


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
pipe = None
recording = True
printerror = True

capture = cv.CaptureFromCAM(0)
width = cv.GetCaptureProperty(capture, cv.CV_CAP_PROP_FRAME_WIDTH)
height = cv.GetCaptureProperty(capture, cv.CV_CAP_PROP_FRAME_HEIGHT)
filename = 'CamCapture.avi'

command = [ "/opt/clue/bin/ffmpeg",
	'-y',
	'-f', 'rawvideo',
	'-s', '640x480',
	'-pix_fmt', 'bgr24',
	'-r', '15',
	'-i', '-',
	'-an',
	'-vcodec', 'mpeg4',
	filename]

pipe = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
timing = datetime.datetime.now()

while recording:
	try:
		image = cv.QueryFrame(capture)
			
		if framesno % 100 == 0:
			print ("Resources datagram for " + str(framesno) + " frames in " + str(round((datetime.datetime.now() - timing).total_seconds(), 2)) + " sec.: " + json.dumps(memoryinfo()))
			timing = datetime.datetime.now()
		
		if pipe is not None:
			pipe.stdin.write(image.tostring())
		
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
	except:
		traceback.print_exc()
		sys.exit(1)

if pipe is not None:
	pipe.stdin.close()
	pipe.stderr.close()
