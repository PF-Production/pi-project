from mp3_player import MP3Player
import time

def main():
    print("Hello from pi-project!")

if __name__ == "__main__":
    main()
    player = MP3Player("./kb.mp3.wav", second_path="./Karla Bidi - Mono Vox.wav", volume=0.1)
    player.play_loop()
    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        player.stop()