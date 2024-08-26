from time import sleep, time
from labinstruments.Instrument import SCPISerialInstrument

class Agilent33250A(SCPISerialInstrument):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, instrument_manufacturer='Agilent', instrument_model='33250A', **kwargs)

	def set_shape(self, shape:str):
		self.write(f'FUNC {shape.upper()}')
		if shape.lower() == 'user':
			self.write('FUNC:USER volatile') # From all the arbitrary waveforms, select the one in the volatile memory.

	def set_frequency(self, hertz:float):
		self.write(f'FREQ {hertz:e}')

	def set_amplitude(self, volts_pp:float):
		self.write('VOLT:UNIT VPP') # Make sure it will be volts peak to peak.
		self.write(f'VOLT {volts_pp:e}')

	def set_offset(self, volts:float):
		self.write(f'VOLT:OFFS {volts:e}')

	def set_pulse_width(self, seconds:float):
		self.write(f'PULS:WIDT {seconds:e}')

	def set_output(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError('`status` must be either "on" or "off". ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'OUTP {status}')

	def set_burst(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError(f'`status` must be either "on" or "off", received {repr(status)}. ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'BURS:STAT {status}')

	def set_burst_mode(self, mode:str):
		self.write(f'BURS:MODE {mode.upper()}')

	def set_burst_n_cycles(self, n:int):
		self.write(f'BURS:NCYC {int(n)}')

	def force_trigger(self):
		self.write('*TRG')
		self.write('*WAI')

	def wait_for_trigger(self, timeout=None, should_stop=lambda: False):
		""" Wait until the triggering has finished or timeout is reached.
		:param timeout: The maximum time the waiting is allowed to take. If
						timeout is exceeded, a TimeoutError is raised. If
						timeout is set to zero, no timeout will be used.
		:param should_stop: Optional function (returning a bool) to allow the
							waiting to be stopped before its end.
		"""
		self.write("*OPC?")
		t0 = time()
		while True:
			try:
				ready = bool(self.read())
			except Exception:
				ready = False
			if ready:
				return
			if timeout is not None and time() - t0 > timeout:
				raise TimeoutError("Timeout expired while waiting for the Agilent 33220A to finish the triggering.")

	def output_triggered(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError('`status` must be either "on" or "off". ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'OUTP:TRIG {status}')

	def configure_arbitrary_waveform(self, samples_in_volt:list[float]):
		# Compute normalized samples between -1 and 1:
		maximum_absolute_voltage = [abs(s) for s in samples_in_volt]
		maximum_absolute_voltage = max(maximum_absolute_voltage)
		samples = samples_in_volt
		samples = [s/maximum_absolute_voltage for s in samples]
		self.load_arbitrary_waveform_samples(samples)
		# Now configure offset and amplitude to obtain the desired voltage levels:
		self.set_offset(volts=0)
		self.set_amplitude(volts_pp=max(samples_in_volt)-min(samples_in_volt))
		self.set_shape('user') # Select arbitrary waveform source.

	def load_arbitrary_waveform_samples(self, samples:list[float]):
		self.write_without_checking_errors('DATA VOLATILE, ' + ', '.join([str(_) for _ in samples]))
		self.write_without_checking_errors('*WAI')
		self.check_whether_error()

def example():
	A = Agilent33250A(
		Serial_kwargs = dict(
			port = '/dev/ttyUSB1',
			timeout = 1,
			dsrdtr = True,
			baudrate = 9600,
		),
	)
	print(f'Connected with {A.idn}')
	A.reset()

	A.set_output('off')

	A.configure_arbitrary_waveform([0,-1,0,-2,0,0])
	A.set_burst('on')
	A.set_burst_mode('triggered')
	A.set_burst_n_cycles(2)
	A.write('TRIG:SOURCE BUS') # Select trigger source from software.
	A.set_frequency(1e3)
	A.set_output('on')
	A.force_trigger()

if __name__ == '__main__':
	import sys
	import logging

	logging.basicConfig(
		stream = sys.stderr,
		level = logging.DEBUG,
		format = '%(asctime)s|%(levelname)s|%(message)s',
		datefmt = '%H:%M:%S',
	)

	example()
