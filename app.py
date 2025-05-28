from flask import Flask, request, jsonify, send_from_directory
import openai
import os
import io
import base64
from PIL import Image
from flask_cors import CORS
import logging
from imagededup.methods import PHash
import requests
import subprocess
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Configure CORS to allow all origins
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept"]
    }
})

# Initialize the PHash object
phasher = PHash()

def encode_image(image):
    try:
        image = image.resize((256, 256))
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encoding image: {str(e)}")
        raise

@app.route('/api/describe-image', methods=['POST', 'OPTIONS'])
def describe_image():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Get image file and prompt from request
        if 'image' not in request.files:
            logger.error("No image file in request")
            return jsonify({'error': 'No image file provided'}), 400
            
        image_file = request.files['image']
        prompt = request.form.get('prompt', 'Briefly describe the picture')
        
        logger.info(f"Processing image with prompt: {prompt}")
        logger.info(f"Received image file: {image_file.filename}")
        
        # Read and encode image
        try:
            image = Image.open(image_file)
            base64_image = encode_image(image)
            logger.info("Image successfully encoded")
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return jsonify({'error': 'Failed to process image'}), 400
        
        # Initialize OpenAI client
        try:
            client = openai.OpenAI(
                api_key="sk-74f4ad2a3c1c4d3d80665aa0403a0892",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            return jsonify({'error': 'Failed to initialize API client'}), 500
        
        # Generate description
        try:
            logger.info("Sending request to OpenAI API")
            completion = client.chat.completions.create(
                model="qwen-vl-plus",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ]
            )
            
            description = completion.choices[0].message.content
            logger.info("Successfully generated description")
            
            return jsonify({
                'description': description
            })
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return jsonify({'error': 'Failed to generate description from API'}), 500
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/find-duplicates', methods=['POST'])
def find_duplicates():
    try:
        data = request.json
        if not data or 'photos' not in data:
            return jsonify({'error': 'No photos data provided'}), 400
            
        photos = data.get('photos', [])
        if not photos:
            return jsonify({'error': 'Empty photos list'}), 400
        
        # Create a temporary directory to store the images
        temp_dir = 'temp_images'
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save images to temporary files
        image_paths = []
        for i, photo in enumerate(photos):
            try:
                # Convert base64 to image file
                if 'src' not in photo:
                    continue
                    
                # Handle both base64 and URL formats
                if photo['src'].startswith('data:image'):
                    # Base64 format
                    image_data = base64.b64decode(photo['src'].split(',')[1])
                else:
                    # URL format
                    response = requests.get(photo['src'])
                    image_data = response.content
                
                image_path = os.path.join(temp_dir, f'image_{i}.jpg')
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                
                # Get actual file size
                file_size = os.path.getsize(image_path)
                image_paths.append((image_path, i, file_size))  # Store path, index, and size
            except Exception as e:
                print(f"Error processing photo {i}: {str(e)}")
                continue
        
        if not image_paths:
            return jsonify({'error': 'No valid images to process'}), 400
        
        try:
            # Generate encodings for all images
            encodings = phasher.encode_images(image_dir=temp_dir)
            
            # Find duplicates with a very lenient threshold
            duplicates = phasher.find_duplicates(
                encoding_map=encodings,
                max_distance_threshold=15  # Very lenient threshold to find similar images
            )
            
            print("Found duplicates:", duplicates)  # Debug print
            
            # Group similar photos
            groups = []
            processed = set()
            
            # Process each original photo and its duplicates
            for original, dups in duplicates.items():
                if not dups:  # Skip if no duplicates
                    continue
                
                # 拼接完整路径
                original_path = os.path.join(temp_dir, original)
                original_info = next((path_info for path_info in image_paths if path_info[0] == original_path), None)
                if original_info is None:
                    continue
                
                original_index, original_size = original_info[1], original_info[2]
                
                # Create a new group
                group = {
                    'photos': [{
                        'src': photos[original_index]['src'],
                        'name': photos[original_index]['name'],
                        'size': original_size
                    }]
                }
                
                # Add duplicates to the group
                for dup in dups:
                    dup_path = os.path.join(temp_dir, dup)
                    if dup_path in processed:
                        continue
                    dup_info = next((path_info for path_info in image_paths if path_info[0] == dup_path), None)
                    if dup_info is not None:
                        dup_index, dup_size = dup_info[1], dup_info[2]
                        group['photos'].append({
                            'src': photos[dup_index]['src'],
                            'name': photos[dup_index]['name'],
                            'size': dup_size
                        })
                        processed.add(dup_path)
                
                processed.add(original_path)
                if len(group['photos']) > 1:  # Only add groups with more than one photo
                    groups.append(group)
            
            print("Created groups:", groups)  # Debug print
            
            # Clean up temporary files
            for path, _, _ in image_paths:
                try:
                    os.remove(path)
                except:
                    pass
            
            if not groups:
                return jsonify({'error': 'No similar photos found'}), 404
            
            # 找出没有重复的照片
            others = []
            for filename, dups in duplicates.items():
                if not dups:
                    # 拼接完整路径，找到index
                    original_path = os.path.join(temp_dir, filename)
                    original_info = next((path_info for path_info in image_paths if path_info[0] == original_path), None)
                    if original_info is not None:
                        original_index, original_size = original_info[1], original_info[2]
                        others.append({
                            'src': photos[original_index]['src'],
                            'name': photos[original_index]['name'],
                            'size': original_size
                        })
            
            return jsonify({'groups': groups, 'others': others})
            
        except Exception as e:
            print(f"Error in duplicate detection: {str(e)}")
            return jsonify({'error': f'Error in duplicate detection: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/api/apply-optimization', methods=['POST'])
def apply_optimization():
    try:
        data = request.json
        photos_to_keep = data.get('photosToKeep', [])
        photos_to_delete = data.get('photosToDelete', [])
        
        # Here you would implement the actual file deletion logic
        # For now, we'll just return success
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/style-transfer', methods=['POST'])
def style_transfer():
    try:
        if 'style' not in request.files or 'content' not in request.files:
            return jsonify({'error': 'Missing style or content image'}), 400
            
        style_file = request.files['style']
        content_file = request.files['content']
        preprocessor = request.form.get('preprocessor', 'Contour')
        
        if not style_file or not content_file:
            return jsonify({'error': 'Invalid file upload'}), 400
            
        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save uploaded files with unique names
        style_path = os.path.join(temp_dir, f'style_{int(time.time())}.jpg')
        content_path = os.path.join(temp_dir, f'content_{int(time.time())}.jpg')
        
        style_file.save(style_path)
        content_file.save(content_path)
        
        # Get the original content file path from the form data
        content_original_path = request.form.get('contentPath', '')
        if not content_original_path:
            return jsonify({'error': 'Content file path not provided'}), 400
            
        # Create output path in temp directory
        content_name, content_ext = os.path.splitext(content_original_path)
        output_filename = f"{content_name}_styled{content_ext}"
        output_path = os.path.join(temp_dir, output_filename)
        
        # Run style transfer command
        cmd = f'python styleshot_image_driven_demo.py --style "{style_path}" --content "{content_path}" --preprocessor "{preprocessor}" --output "{output_path}"'
        
        logger.info(f"Running command: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Style transfer failed: {result.stderr}")
            return jsonify({'error': f'Style transfer failed: {result.stderr}'}), 500
            
        # Return the URL to access the result
        output_url = f'/temp/{output_filename}'
        
        return jsonify({
            'success': True,
            'outputUrl': output_url
        })
        
    except Exception as e:
        logger.error(f"Error in style transfer: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/temp/<path:filename>')
def serve_temp_file(filename):
    return send_from_directory('temp', filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0') 