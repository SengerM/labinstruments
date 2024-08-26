from time import sleep, time
from .Instrument import SCPISerialInstrument

class Keithley2700(SCPISerialInstrument):
	def set_what_and_range_and_resolution(self, what:str, range:float, resolution:float):
		self.write(f'CONF:{what} {range:e}, {resolution:e}')

	def measure(self, what:str, range:float, resolution:float)->float:
		self.write('FORM:ELEM READ') # Configure the instrument to return just the value of the measurement.
		value_returned_by_the_instrument = self.query_without_checking_errors(f'MEAS:{what}? {range:e}, {resolution:e}')
		value_returned_by_the_instrument = float(value_returned_by_the_instrument)
		return value_returned_by_the_instrument

	def measure_N_samples_using_the_buffer(self, measure_kwargs:dict, n_samples:int, timeout=None)->list:
		self.set_what_and_range_and_resolution(**measure_kwargs)
		self.write('INIT:CONTINUOUS off') # Stop the DMM.
		self.write('TRAC:CLEAR') # Clear the buffer.
		self.write('TRAC:CLE:AUTO on') # Enable buffer.
		self.write(f'TRAC:POINTS {n_samples}') # Set number of samples to be stored.
		self.write('TRAC:FEED sense') # Set source of data to store in the buffer.
		self.write('TRAC:FEED:CONTROL next') # Set the buffer to store the next N incoming data samples, then stop storing.
		self.write('INIT:CONTINUOUS on') # Start the DMM.

		# Wait until the instrument has collected all the required samples:
		BYTES_PER_SAMPLE = 16 # I measured this using the command 'TRAC:FREE?'
		t_start = time()
		sleeptime = .01
		while int(self.query('TRAC:FREE?').split(',')[-1])/BYTES_PER_SAMPLE < n_samples:
			if timeout is not None and time()-t_start > timeout:
				raise RuntimeError(f'Timeout measuring n_samples={n_samples}.')
			sleep(sleeptime)
			sleeptime = sleeptime*2 if sleeptime < 1 else sleeptime # Increase the sleeptime so it is not using the CPU all the time if the measurement is long.

		self.write('FORM:ELEM READ') # Configure the instrument to return just the value of the measurement.
		data = self.query('TRAC:DATA?')
		data = [float(_) for _ in data.split(',')]

		if len(data) != n_samples:
			raise RuntimeError(f'Could not get the requested number of samples from the instrument. Requested number was n_samples={n_samples} while the number of retrieved samples is {len(data)}. ')
		return data

def example():
	import numpy

	k = Keithley2700(
		Serial_kwargs = dict(
			port = '/dev/ttyUSB0',
			timeout = 1,
			xonxoff = True,
			baudrate = 9600,
			# ~ write_timeout = 1,
		),
	)
	for _ in range(9):
		print(f'Connected with {k.idn}')

	k.reset()

	data = k.measure_N_samples_using_the_buffer(
		measure_kwargs = dict(
			what = 'resistance',
			range = 200,
			resolution = 1,
		),
		n_samples = 11,
	)
	print('data = ', data)
	print(f'R = {numpy.mean(data)} ± {numpy.std(data)} Ohm')

	R = k.measure(
		what = 'resistance',
		range = 200,
		resolution = 1,
	)
	print(f'Just measured R = {R}')

if __name__ == '__main__':
	example()
