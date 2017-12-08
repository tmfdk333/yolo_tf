import numpy as np
import os

def cfg_yielder(model, undiscovered = True):
	"""
	yielding each layer information, i.e. yielding type & size
	of each layer of `model`.
	Because of different reasons, it is not always be the ideal 
	case that following .cfg file will successfully match the 
	size of .weights file, so one would need to investigate the
	.weights file if s/he is parsing the .cfg file for the first 
	time (undiscovered = True) in order to adjust the parsing 
	appropriately.
	"""

	# Step 1: parsing cfg file
	with open('configs/yolo-{}.cfg'.format(model), 'rb') as f:
		lines = f.readlines()

	s = [] # contains layers' info
	S = int() # the number of grid cell
	add = dict()
	for line in lines:
		line = line.strip()
		if 'side' in line:
			S = int(line.split('=')[1].strip())
		if '[' in line:
			if add != {}:
				s += [add]
			add = dict()
		else:
			try:
				i = float(line.split('=')[1].strip())
				if i == int(i): i = int(i)
				add[line.split('=')[0]] = i
			except:
				try:
					if line.split('=')[1] == 'leaky' and 'output' in add:
						add[line.split('=')[0]] = line.split('=')[1]
				except:
					pass
	yield S

	# Step 2: investigate the weight file
	weightf = 'yolo-{}.weights'.format(model)
	if undiscovered:
		allbytes = os.path.getsize('yolo-{}.weights'.format(model))
		allbytes /= 4 # each float is 4 byte
		allbytes -= 4 # the first 4 bytes are darknet specifications
		last_convo = int() 
		for i, d in enumerate(s):
			if len(d) == 4:
				last_convo = i # the index of last convolution layer
		flag = False
		channel = 3 # initial number of channel in the tensor volume
		out = int() 
		for i, d in enumerate(s):
    		# for each iteration in this loop
			# allbytes will be gradually subtracted
			# by the size of the corresponding layer (d)
			# except for the 1st dense layer
			# it should be what remains after subtracting
			# all other layers
			if len(d) == 4:
				allbytes -= d['size'] ** 2 * channel * d['filters']
				allbytes -= d['filters']
				channel = d['filters']
			elif 'output' in d: # this is a dense layer
				if flag is False: # this is the first dense layer
					out = out1 = d['output'] # output unit of the 1st dense layer
					flag = True # mark that the 1st dense layer is passed
					continue # don't do anything with the 1st dense layer
				allbytes -= out * d['output']
				allbytes -= d['output']
				out = d['output']
		allbytes -= out1 # substract the bias
		if allbytes <= 0:
				message = "Error: yolo-{}.cfg suggests a bigger size"
				message += " than yolo-{}.weights actually is"
				print message.format(model, model)
				assert allbytes > 0
		# allbytes is now = I * out1
		# where I is the input size of the 1st dense layer
		# I is also the volume of the last convolution layer
		# I = size * size * channel
		size = (np.sqrt(allbytes/out1/channel)) 
		size = int(size)
		n = last_convo + 1
		while 'output' not in s[n]:
			size *= s[n].get('size',1)
			n += 1
	else:
		last_convo = None
		size = None

	# Step 3: Yielding config
	w = 448
	h = 448
	c = 3
	l = w * h * c
	flat = False
	yield ['CROP']
	for i, d in enumerate(s):
		#print w, h, c, l
		flag = False
		if len(d) == 4:
			mult = (d['size'] == 3) 
			mult *= (d['stride'] != 2) + 1.
			if d['size'] == 1: d['pad'] = 0
			new = (w + mult * d['pad'] - d['size'])
			new /= d['stride']
			new = int(np.floor(new + 1.))
			if i == last_convo:
				d['pad'] = -size
				new = size
			yield ['conv', d['size'], c, d['filters'], 
				    h, w, d['stride'], d['pad']]	
			w = h = new
			c = d['filters']
			l = w * h * c
			#print w, h, c
		if len(d) == 2:
			if 'output' not in d:
				yield ['pool', d['size'], 0, 
					0, 0, 0, d['stride'], 0]
				new = (w * 1.0 - d['size'])/d['stride'] + 1
				new = int(np.floor(new))
				w = h = new
				l = w * h * c
			else:
				if not flat:
					flat = True
					yield ['FLATTEN']
				yield ['conn', 0, 0,
				0, 0, 0, l, d['output']]
				l = d['output']
				if 'activation' in d:
					yield ['LEAKY']
		if len(d) == 1:
			if 'output' not in d:
				yield ['DROPOUT']
			else:
				if not flat:
					flat = True
					yield ['FLATTEN']
				yield ['conn', 0, 0,
				0, 0, 0, l, d['output']]
				l = d['output']