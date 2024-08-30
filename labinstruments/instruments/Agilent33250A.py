from time import sleep, time
from labinstruments.Instrument import SCPISerialInstrument

class Agilent33250A(SCPISerialInstrument):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, instrument_manufacturer='Agilent', instrument_model='33250A', **kwargs)

	def apply(self, function:str, frequency:float, volt_pp:float, volt_offset:float):
		"""Send the `APPLY` command to the instrument. For details, see [page 144 of the user manual](https://www.keysight.com/se/en/assets/9018-03925/user-manuals/9018-03925.pdf?success=true)."""
		self.write('VOLT:UNIT VPP') # Make sure it will be volts peak to peak.
		self.write(f'APPLY:{function} {frequency:e}, {volt_pp:e}, {volt_offset:e}')

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

	def force_trigger(self, block_execution_timeout:float=None):
		self.write('*TRG')
		if block_execution_timeout is not None:
			self.wait_until_all_comands_have_been_executed(timeout=block_execution_timeout)

	def output_triggered(self, status:str):
		if status.lower() not in {'on','off'}:
			raise ValueError('`status` must be either "on" or "off". ')
		status = 1 if status.lower()=='on' else 0
		self.write(f'OUTP:TRIG {status}')

	def configure_arbitrary_waveform(self, samples_in_volt:list[float], frequency:float):
		# Compute normalized samples between -1 and 1:
		maximum_absolute_voltage = [abs(s) for s in samples_in_volt]
		maximum_absolute_voltage = max(maximum_absolute_voltage)
		samples = samples_in_volt
		samples = [s/maximum_absolute_voltage for s in samples]
		self.load_arbitrary_waveform_samples(samples)
		self.write('FUNC:USER volatile') # From all the arbitrary waveforms, select the one in the volatile memory.
		self.apply(
			function = 'user',
			frequency = frequency,
			volt_pp = (max(samples_in_volt)-min(samples_in_volt))/2,
			volt_offset = 0,
		)

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

	A.set_output('off')

	A.configure_arbitrary_waveform([0,3,0,-2,0,0]*33, frequency=100e3)
	A.set_burst('on')
	A.set_burst_mode('triggered')
	A.write('BURSt:INTernal:PERiod 111') # I don't fully understand why we need this, but without this it does not let you to put many burst cycles...
	A.set_burst_n_cycles(1e5)
	A.write('TRIG:SOURCE BUS') # Select trigger source from software.
	A.set_output('on')
	print('Forcing trigger...')
	A.force_trigger()
	print('Done!')

if __name__ == '__main__':
	import sys
	import logging

	# ~ logging.basicConfig(
		# ~ stream = sys.stderr,
		# ~ level = logging.DEBUG,
		# ~ format = '%(asctime)s|%(levelname)s|%(message)s',
		# ~ datefmt = '%H:%M:%S',
	# ~ )

	example()
