
from pydub import AudioSegment
from pydub.effects import low_pass_filter, high_pass_filter

# Load the original WAV file
input_path = "./kb.mp3.wav"
audio = AudioSegment.from_wav(input_path)

"""
No EQ applied; export original audio
"""
output_path = "./kb_eq.wav"
audio.export(output_path, format="wav")

print(f"Original audio saved to {output_path}")
