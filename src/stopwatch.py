import cv2
import numpy as np
import time

# Stopwatch state
start_time = 0
running = False
elapsed_time = 0

def draw_button(img, text, position, size, color):
    x, y = position
    w, h = size
    cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
    cv2.putText(img, text, (x + 10, y + h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

def check_button(position, mouse_position, size):
    x, y = position
    w, h = size
    mx, my = mouse_position
    return x < mx < x + w and y < my < y + h

def format_time(seconds):
    milliseconds = int((seconds - int(seconds)) * 10000)  # Four decimal places
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return "%02d:%02d:%02d.%04d" % (hours, minutes, seconds, milliseconds)

# Mouse callback function
def on_mouse(event, x, y, flags, param):
    global running, start_time, elapsed_time
    if event == cv2.EVENT_LBUTTONDOWN:
        if check_button((10, 10), (x, y), (60, 30)):  # Start
            if not running:
                start_time = time.time() - elapsed_time
                running = True
        elif check_button((80, 10), (x, y), (60, 30)):  # Stop
            if running:
                elapsed_time = time.time() - start_time
                running = False
        elif check_button((150, 10), (x, y), (60, 30)):  # Reset
            running = False
            elapsed_time = 0

# Create a window and set a mouse callback
cv2.namedWindow("Stopwatch")
cv2.setMouseCallback("Stopwatch", on_mouse)

while True:
    img = np.zeros((100, 300, 3), dtype=np.uint8)

    # Draw buttons
    draw_button(img, "Start", (10, 10), (60, 30), (0, 128, 0))
    draw_button(img, "Stop", (80, 10), (60, 30), (0, 0, 128))
    draw_button(img, "Reset", (150, 10), (60, 30), (128, 128, 0))

    # Update the stopwatch
    if running:
        elapsed_time = time.time() - start_time

    # Display the stopwatch
    cv2.putText(img, format_time(elapsed_time), (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imshow("Stopwatch", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()