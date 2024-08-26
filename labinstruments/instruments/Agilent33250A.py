from time import sleep, time
from labinstruments.Instrument import SCPISerialInstrument

class Agilent33250A(SCPISerialInstrument):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, instrument_manufacturer='Agilent', instrument_model='33250A', **kwargs)

	def apply(self, function:str, frequency:float, volt_pp:float, volt_offset:float):
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

	def force_trigger(self):
		self.write('*TRG')
		self.write('*WAI')

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
	A.reset()

	A.set_output('off')

	A.configure_arbitrary_waveform([0,3,0,-2,0,0], frequency=1e6)
	A.set_burst('on')
	A.set_burst_mode('triggered')
	A.set_burst_n_cycles(2222)
	A.write('TRIG:SOURCE BUS') # Select trigger source from software.
	A.set_output('on')
	A.force_trigger()

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
