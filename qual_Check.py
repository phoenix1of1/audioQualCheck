import os
import subprocess
from PIL import Image, ImageDraw
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

def get_audio_info(file_path):
    """Extract audio information using ffmpeg."""
    analysis = {}
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
    return analysis

def generate_spectrogram(file_path, output_dir):
    """Generate a spectrogram image using ffmpeg."""
    spectrogram_file = os.path.join(output_dir, os.path.basename(os.path.splitext(file_path)[0]) + '_spectrogram.png')
    subprocess.run(['ffmpeg', '-i', file_path, '-lavfi', 'showspectrumpic=s=2048x1024:fscale=lin:legend=1', spectrogram_file], check=True)
    return spectrogram_file

def draw_line_on_spectrogram(spectrogram_file):
    """Draw a line on the spectrogram image within the bounding box."""
    image = Image.open(spectrogram_file)
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 142, 2188, 65, 225  # Adjusted bottom by adding 100 pixels
    line_y = top + (bottom - top) // 8  # Change to 1/8th of the height within the box
    draw.line((left, line_y, right, line_y), fill="red", width=2)
    image.save(spectrogram_file)

def analyze_spectrogram(spectrogram_file, log_file):
    """Analyze the spectrogram for high-frequency content and log non-black pixels."""
    image = Image.open(spectrogram_file)
    left, right, top, bottom = 142, 2188, 65, 225  # Adjusted bottom by adding 100 pixels
    high_freq_content = False
    log_file.write(f"Non-black pixels in {os.path.basename(spectrogram_file)}:\n")
    for x in range(left, right + 1):
        for y in range(top, bottom + 1):
            pixel = image.getpixel((x, y))
            if pixel >= (0, 1, 26):
                high_freq_content = True
                log_file.write(f"  ({x}, {y}): {pixel}\n")
    log_file.write("\n")
    return high_freq_content

def analyze_flac(file_path, output_dir, log_file):
    """Analyze a FLAC file and generate a spectrogram."""
    analysis = get_audio_info(file_path)
    analysis['spectrogram'] = generate_spectrogram(file_path, output_dir)
    analysis['high_freq_content'] = analyze_spectrogram(analysis['spectrogram'], log_file)
    analysis['avg_bitrate'] = calculate_average_bitrate(file_path)

    # Compare bitrates with a tolerance of 5%
    tolerance = 0.05
    header_bitrate = analysis['bit_rate']
    avg_bitrate = analysis['avg_bitrate']
    analysis['bitrate_mismatch'] = abs(header_bitrate - avg_bitrate) / header_bitrate > tolerance

    # Draw the line on the spectrogram after analysis
    draw_line_on_spectrogram(analysis['spectrogram'])

    return analysis

def check_directory(directory, output_dir):
    """Check all FLAC files in a directory."""
    flac_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".flac")]
    results = {}

    # Open log file for non-black pixels
    pixel_log_file_path = os.path.join(output_dir, 'non_black_pixels_log.txt')
    failed_log_file_path = os.path.join(output_dir, 'failed_tracks_log.txt')
    with open(pixel_log_file_path, 'w', encoding='utf-8') as pixel_log_file, open(failed_log_file_path, 'w', encoding='utf-8') as failed_log_file:
        for flac_file in flac_files:
            results[flac_file] = analyze_flac(flac_file, output_dir, pixel_log_file)
            if not results[flac_file]['high_freq_content']:
                failed_log_file.write(f"{os.path.basename(flac_file)}\n")

    # Write results to analysis log file
    analysis_log_file_path = os.path.join(output_dir, 'analysis_log.txt')
    with open(analysis_log_file_path, 'w', encoding='utf-8') as analysis_log_file:
        for file, analysis in results.items():
            if analysis:
                analysis_log_file.write(f"{os.path.basename(file)}:\n")
                analysis_log_file.write(f"  Bit Rate: {analysis.get('bit_rate')} kbps\n")
                analysis_log_file.write(f"  Average Bit Rate: {analysis.get('avg_bitrate')} kbps\n")
                analysis_log_file.write(f"  Sample Rate: {analysis.get('sample_rate')} Hz\n")
                analysis_log_file.write(f"  Channels: {analysis.get('channels')}\n")
                analysis_log_file.write(f"  Spectrogram: {analysis.get('spectrogram')}\n")
                analysis_log_file.write(f"  High Frequency Content: {'Yes' if analysis.get('high_freq_content') else 'No'}\n")
                analysis_log_file.write(f"  Bitrate Mismatch: {'Yes' if analysis.get('bitrate_mismatch') else 'No'}\n")
                
                # Check if the file passes the checks
                passes_checks = (
                    analysis.get('bit_rate', 0) > 220 and
                    analysis.get('avg_bitrate', 0) > 300 and  # Changed from 450 to 300
                    analysis.get('sample_rate', 0) >= 44100 and
                    analysis.get('channels') is not None and
                    analysis.get('spectrogram') is not None and
                    analysis.get('high_freq_content') and
                    not analysis.get('bitrate_mismatch')
                )
                analysis_log_file.write(f"  Passes Checks: {'Yes' if passes_checks else 'No'}\n")
                
                if not passes_checks:
                    analysis_log_file.write("  Fails on:\n")
                    if analysis.get('bit_rate', 0) <= 220:
                        analysis_log_file.write("    - Bit Rate is less than or equal to 220 kbps\n")
                    if analysis.get('avg_bitrate', 0) <= 300:  # Changed from 450 to 300
                        analysis_log_file.write("    - Average Bit Rate is less than or equal to 300 kbps\n")
                    if analysis.get('sample_rate', 0) < 44100:
                        analysis_log_file.write("    - Sample Rate is less than 44100 Hz\n")
                    if analysis.get('channels') is None:
                        analysis_log_file.write("    - Channels information is missing\n")
                    if analysis.get('spectrogram') is None:
                        analysis_log_file.write("    - Spectrogram is missing\n")
                    if not analysis.get('high_freq_content'):
                        analysis_log_file.write("    - High Frequency Content is missing\n")
                    if analysis.get('bitrate_mismatch'):
                        analysis_log_file.write("    - Bitrate Mismatch\n")
                analysis_log_file.write("\n")
            else:
                analysis_log_file.write(f"Failed to analyze {os.path.basename(file)}.\n\n")

    return results

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    directory = filedialog.askdirectory(title="Select the directory containing FLAC files", initialdir="L:/Uploads")
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
                    analysis.get('bit_rate', 0) > 220 and
                    analysis.get('avg_bitrate', 0) > 300 and  # Changed from 450 to 300
                    analysis.get('sample_rate', 0) >= 44100 and
                    analysis.get('channels') is not None and
                    analysis.get('spectrogram') is not None and
                    analysis.get('high_freq_content') and
                    not analysis.get('bitrate_mismatch')
                )
                print(f"  Passes Checks: {'Yes' if passes_checks else 'No'}\n")
            else:
                print(f"Failed to analyze {file}.\n")
