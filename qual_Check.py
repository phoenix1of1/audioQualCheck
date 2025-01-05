import os
import subprocess
from PIL import Image
import tkinter as tk
from tkinter import filedialog

def calculate_average_bitrate(file_path):
    # Get file size in kilobits
    file_size = os.path.getsize(file_path) * 8 / 1024  # Convert bytes to kilobits

    # Get audio duration using ffprobe
    command = f'ffprobe -i "{file_path}" -show_entries format=duration -v quiet -of csv="p=0"'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    duration = float(result.stdout.strip())

    # Calculate average bitrate in kbps
    avg_bitrate = file_size / duration
    return avg_bitrate

def analyze_flac(file_path, output_dir):
    """Analyze a FLAC file and generate a spectrogram."""
    analysis = {}
    try:
        # Get audio file information
        result = subprocess.run(['ffmpeg', '-i', file_path], stderr=subprocess.PIPE, text=True, encoding='utf-8')
        for line in result.stderr.split('\n'):
            if 'bitrate:' in line:
                analysis['bit_rate'] = int(line.split('bitrate:')[1].strip().split(' ')[0])  # Already in kbps
            if 'Stream #0:0' in line and 'Audio:' in line:
                parts = line.split(',')
                for part in parts:
                    if 'Hz' in part:
                        analysis['sample_rate'] = int(part.strip().split(' ')[0])
                    if 'stereo' in part or 'mono' in part:
                        analysis['channels'] = part.strip()

        # Generate spectrogram
        spectrogram_file = os.path.join(output_dir, os.path.basename(os.path.splitext(file_path)[0]) + '_spectrogram.png')
        subprocess.run(['ffmpeg', '-i', file_path, '-lavfi', 'showspectrumpic=s=1024x512', spectrogram_file], check=True)
        analysis['spectrogram'] = spectrogram_file

        # Analyze spectrogram for high-frequency content
        image = Image.open(spectrogram_file)
        width, height = image.size
        high_freq_content = False
        for x in range(width):
            for y in range(height // 2, height):  # Check the upper half of the spectrogram
                if image.getpixel((x, y)) != (0, 0, 0):  # Non-black pixel indicates high-frequency content
                    high_freq_content = True
                    break
            if high_freq_content:
                break
        analysis['high_freq_content'] = high_freq_content

        # Calculate average bitrate
        avg_bitrate = calculate_average_bitrate(file_path)
        analysis['avg_bitrate'] = avg_bitrate

        # Compare bitrates with a tolerance of 5%
        tolerance = 0.05
        header_bitrate = analysis['bit_rate']
        if abs(header_bitrate - avg_bitrate) / header_bitrate > tolerance:
            analysis['bitrate_mismatch'] = True
        else:
            analysis['bitrate_mismatch'] = False

    except subprocess.CalledProcessError as e:
        print(f"Error generating spectrogram for {file_path}: {e}")
        analysis['spectrogram'] = None
        analysis['high_freq_content'] = False
        analysis['avg_bitrate'] = None
        analysis['bitrate_mismatch'] = None

    return analysis

def check_directory(directory, output_dir):
    """Check all FLAC files in a directory."""
    flac_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".flac")]
    results = {}

    for flac_file in flac_files:
        print(f"Analyzing {flac_file}...")
        results[flac_file] = analyze_flac(flac_file, output_dir)

    # Write results to log file
    log_file_path = os.path.join(output_dir, 'analysis_log.txt')
    with open(log_file_path, 'w', encoding='utf-8') as log_file:
        for file, analysis in results.items():
            if analysis:
                log_file.write(f"{file}:\n")
                log_file.write(f"  Bit Rate: {analysis.get('bit_rate')} kbps\n")
                log_file.write(f"  Average Bit Rate: {analysis.get('avg_bitrate')} kbps\n")
                log_file.write(f"  Sample Rate: {analysis.get('sample_rate')} Hz\n")
                log_file.write(f"  Channels: {analysis.get('channels')}\n")
                log_file.write(f"  Spectrogram: {analysis.get('spectrogram')}\n")
                log_file.write(f"  High Frequency Content: {'Yes' if analysis.get('high_freq_content') else 'No'}\n")
                log_file.write(f"  Bitrate Mismatch: {'Yes' if analysis.get('bitrate_mismatch') else 'No'}\n")
                
                # Check if the file passes the checks
                passes_checks = (
                    analysis.get('bit_rate', 0) > 500 and
                    analysis.get('sample_rate', 0) >= 44100 and
                    analysis.get('channels') is not None and
                    analysis.get('spectrogram') is not None and
                    analysis.get('high_freq_content') and
                    not analysis.get('bitrate_mismatch')
                )
                log_file.write(f"  Passes Checks: {'Yes' if passes_checks else 'No'}\n\n")
            else:
                log_file.write(f"Failed to analyze {file}.\n\n")

    return results

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    directory = filedialog.askdirectory(title="Select the directory containing FLAC files")
    if not directory:
        print("No directory selected.")
    elif not os.path.isdir(directory):
        print("Invalid directory path.")
    else:
        # Create output directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, 'analysis_results')
        os.makedirs(output_dir, exist_ok=True)

        results = check_directory(directory, output_dir)
        print("\nAnalysis Complete.\n")

        for file, analysis in results.items():
            if analysis:
                print(f"{file}:")
                print(f"  Bit Rate: {analysis.get('bit_rate')} kbps")
                print(f"  Average Bit Rate: {analysis.get('avg_bitrate')} kbps")
                print(f"  Sample Rate: {analysis.get('sample_rate')} Hz")
                print(f"  Channels: {analysis.get('channels')}")
                print(f"  Spectrogram: {analysis.get('spectrogram')}")
                print(f"  High Frequency Content: {'Yes' if analysis.get('high_freq_content') else 'No'}")
                print(f"  Bitrate Mismatch: {'Yes' if analysis.get('bitrate_mismatch') else 'No'}")
                
                # Check if the file passes the checks
                passes_checks = (
                    analysis.get('bit_rate', 0) > 500 and
                    analysis.get('sample_rate', 0) >= 44100 and
                    analysis.get('channels') is not None and
                    analysis.get('spectrogram') is not None and
                    analysis.get('high_freq_content') and
                    not analysis.get('bitrate_mismatch')
                )
                print(f"  Passes Checks: {'Yes' if passes_checks else 'No'}\n")
            else:
                print(f"Failed to analyze {file}.\n")
