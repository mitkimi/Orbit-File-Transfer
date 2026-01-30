import requests
import os

# Create a test image file
def create_test_image():
    # Create a simple test image using Pillow
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='red')
    img.save('test_image.jpg', 'JPEG')
    return 'test_image.jpg'

def test_upload():
    # Create a test image
    test_file = create_test_image()
    
    # Test upload to the server
    url = 'http://localhost:5000/upload'
    
    with open(test_file, 'rb') as f:
        files = {'files': f}
        response = requests.post(url, files=files)
        
        print(f"Response status: {response.status_code}")
        print(f"Response JSON: {response.json()}")
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    test_upload()