from mp3_player import MP3Player
import time


def main():
    print("Hello from pi-project!")


if __name__ == "__main__":
    main()
    # Replace "hw:1,0" with your actual card number from aplay -l
    player = MP3Player(
        "./kb.mp3.wav",
        second_path="./Karla Bidi - Mono Vox.wav",
        volume=0.1,
        audio_device="hw:1,0",  # Change this to your USB audio card
    )
    player.play_loop()
    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()
