"""Generate a simple test image with shapes to verify the detection pipeline works."""
import cv2
import numpy as np

img = np.zeros((640, 640, 3), dtype=np.uint8)
img[:] = (40, 40, 40)

# Draw a person-like shape (rectangle body + circle head)
cv2.rectangle(img, (250, 200), (390, 550), (0, 140, 255), -1)  # body
cv2.circle(img, (320, 160), 50, (0, 180, 255), -1)             # head
cv2.rectangle(img, (270, 550), (370, 640), (0, 100, 200), -1)  # legs

# Add text
cv2.putText(img, "TEST IMAGE", (180, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 212, 255), 2)
cv2.putText(img, "Upload this to verify pipeline", (100, 620), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 1)

path = "static/uploads/test_sample.jpg"
cv2.imwrite(path, img)
print(f"Test image saved to: {path}")
print("Upload this image at http://127.0.0.1:5000/upload to test the system.")
