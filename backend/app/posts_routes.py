import datetime
import json
import os

import requests
from bson.objectid import ObjectId
from flask import Blueprint, jsonify, request, send_from_directory
from marshmallow import ValidationError

from admin.auth import login_required
from app.config import Config
from repos.repos import get_posts_collection
from schemas.schema import PostSchema, TagSchema

# Check if running locally
if os.path.exists('.env'):
    from dotenv import load_dotenv
    load_dotenv()

# Your hCaptcha secret key (keep this secure and never expose it on the client side)
captcha_secret_key = Config.CAPTCHA_SECRET_KEY

# Now retrieve the MongoDB URI
# mongo_uri = Config.MONGO_URI
secret_key = Config.SECRET_KEY
cdn_key = Config.CDN_KEY
cdn_url = Config.CDN_URL
captcha_url = Config.CAPTCHA_URL

posts_routes_blueprint = Blueprint('posts_routes', __name__)

# Route to serve the React app
@posts_routes_blueprint.route('/')
def index():
    return send_from_directory(os.path.join(posts_routes_blueprint.root_path, 'static'), 'index.html')

# Route to serve static files (JS, CSS, images, etc.)
@posts_routes_blueprint.route('/<path:path>')
def static_files(path):
    return send_from_directory(os.path.join(posts_routes_blueprint.root_path, 'static'), path)

# Use the login_required decorator where needed
@posts_routes_blueprint.route('/protected')
def protected_route():
    return 'This is a protected route.'

# Initialize the schema instance
post_schema = PostSchema()
tag_schema = TagSchema()
# Swagger definition for Post

def upload_image_to_imgbb(image_file):
    """Upload image to ImgBB and return the URL"""
    try:
        files = {'image': image_file}
        data = {'key': cdn_key}
        
        # Extract album ID from URL if needed
        album_id = os.getenv('IMGBB_ALBUM_ID')
        if album_id and album_id.startswith('https://ibb.co/album/'):
            album_id = album_id.split('/')[-1]
        
        if album_id:
            data['album'] = album_id
        
        response = requests.post(cdn_url, files=files, data=data)
        result = response.json()
        
        print(f"ImgBB response: {result}")
        
        if result.get('success'):
            return result['data']['url']
        else:
            print(f"ImgBB upload failed: {result.get('error', 'Unknown error')}")
            return None
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None

# CREATE (Insert a new document)
# Route to create a new post document
@posts_routes_blueprint.route('/api/posts/create', methods=['POST'])
def create():
    """
    Create a new post
    ---
    parameters:
      - name: post
        in: body
        required: true
        schema:
          $ref: '#/definitions/Post'
    responses:
      201:
        description: Post created
      400:
        description: Validation error
    """
    try:
        # Get post data from form
        post_data_str = request.form.get('postData')
        if not post_data_str:
            return jsonify({'error': 'Post data missing'}), 400
            
        post_data = json.loads(post_data_str)
        
        # Validate and deserialize the post data
        data = post_schema.load(post_data)
        hcaptcha_response = data.pop('captchaToken')

        # Skip CAPTCHA verification on localhost
        is_localhost = request.host.startswith('localhost') or request.host.startswith('127.0.0.1')
        
        if not is_localhost:
            if not hcaptcha_response:
                return jsonify({'success': False, 'message': 'CAPTCHA token missing'}), 400

            # Verify the hCaptcha token
            verification_response = requests.post(
                captcha_url,
                data={
                    'secret': captcha_secret_key,
                    'response': hcaptcha_response
                }
            )

            verification_result = verification_response.json()
            if not verification_result.get('success'):
                print(f"CAPTCHA verification failed: {verification_result}")
                return jsonify({'success': False, 'message': 'CAPTCHA verification failed'}), 400

        # Handle image upload if present
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename:
                # Validate file type
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                file_ext = os.path.splitext(image_file.filename.lower())[1]
                if file_ext not in allowed_extensions:
                    return jsonify({'error': 'Invalid file type. Only images are allowed.'}), 400
                
                # Validate file size (5MB limit)
                image_file.seek(0, 2)  # Seek to end
                file_size = image_file.tell()
                image_file.seek(0)  # Reset to beginning
                if file_size > 5 * 1024 * 1024:
                    return jsonify({'error': 'File too large. Maximum size is 5MB.'}), 400
                
                if not cdn_key:
                    print("CDN_KEY not configured, skipping image upload")
                else:
                    image_url = upload_image_to_imgbb(image_file)
                    if image_url:
                        data['content']['image'] = image_url
                        print("Image uploaded successfully")
                    else:
                        print("Failed to upload image to ImgBB, continuing without image")

        data['created_at'] = datetime.datetime.now(datetime.timezone.utc)
        data['status'] = 'approved' #TODO Temporary for alpha testing
        data['optional_tags'] = data.pop('optionalTags', [])
            
        # Insert the data into the collection
        POSTS = get_posts_collection()
        result = POSTS.insert_one(data)
        
        return jsonify({'message': 'Post created', 'post_id': str(result.inserted_id)}), 201
    
    except ValidationError as err:
        print(f"Validation error: {err.messages}")
        return jsonify({'errors': err.messages}), 400
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Example route to retrieve all posts
@login_required
@posts_routes_blueprint.route('/api/posts', methods=['GET'])
def get_posts():
    """
    Get all posts with optional tag filters
    ---
    parameters:
      - name: tag
        in: query
        type: string
        required: false
        description: Single tag to filter posts
      - name: optionalTags
        in: query
        type: array
        items:
          type: string
        collectionFormat: multi  # This allows multiple tags
        required: false
        description: Optional list of tags to filter posts
    responses:
      200:
        description: A list of posts
      400:
        description: input validation error
    """
    try:
        # Get single tag if provided
        tag = request.args.get('tag')
        
        # Get optional tags list if provided
        raw_optional_tags = request.args.getlist('optionalTags')  # This returns a list directly
        
        # Validate and load both tag and optional tags
        args = tag_schema.load({'tag': tag, 'optionalTags': raw_optional_tags})  # Pass both as a dictionary
        tag = args.get('tag')
        optional_tags = args.get('optionalTags', [])

        query = {'status': 'approved'}  # Only return approved posts by default
        
        # Apply tag filters sequentially
        if tag and optional_tags:
            # Both tag and optional tags are provided
            query['$and'] = [
                {'tag': tag},
                {'optional_tags': {'$all': optional_tags}}
            ]
        elif tag:
            # Only single tag is provided
            query['tag'] = tag
        elif optional_tags:
            # Only optional tags are provided
            query['optional_tags'] = {'$all': optional_tags}
        
        POSTS = get_posts_collection()
        posts = list(POSTS.find(query))
        # Convert ObjectId to string to make it JSON serializable
        for post in posts:
            post['_id'] = str(post['_id'])
            # Handle date field conversion - check both formats
            if 'created_at' in post:
                created_at = post.pop('created_at')
                # Convert datetime object to ISO string if needed
                if isinstance(created_at, datetime.datetime):
                    post['createdAt'] = created_at.isoformat()
                else:
                    post['createdAt'] = created_at
            elif 'createdAt' not in post:
                # If no date field exists, use current time as fallback
                post['createdAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # Convert optional_tags to optionalTags for frontend compatibility
            if 'optional_tags' in post:
                post['optionalTags'] = post.pop('optional_tags')
            elif 'optionalTags' not in post:
                post['optionalTags'] = []
        return jsonify(posts), 200

    except ValidationError as err:
        return jsonify({'errors': err.messages}), 400

# UPDATE (Modify a document by ID)
@posts_routes_blueprint.route('/api/posts/update/<id>', methods=['PUT'])
def update_post(id):
    """
    Update a post by ID
    ---
    parameters:
      - name: id
        in: path
        required: true
        type: string
        description: The ID of the post to update
      - name: post
        in: body
        required: true
        schema:
          $ref: '#/definitions/Post'
    responses:
      200:
        description: Post updated
      400:
        description: Invalid post ID or validation error
      404:
        description: Post not found
    """
    try:
        # Validate the post_id to ensure it's a valid ObjectId
        if not ObjectId.is_valid(id):
            return jsonify({'error': 'Invalid post ID'}), 400
        
        # Validate and deserialize the request JSON
        data = post_schema.load(request.json)
        hcaptcha_response = data.pop('captchaToken')

        if not hcaptcha_response:
            return jsonify({'success': False, 'message': 'CAPTCHA token missing'}), 400

        # Verify the hCaptcha token with the hCaptcha verification endpoint
        verification_response = requests.post(
            'https://hcaptcha.com/siteverify',
            data={
                'secret': captcha_secret_key,
                'response': hcaptcha_response
            }
        )

        data['updated_at'] = datetime.datetime.now(datetime.timezone.utc)  # Add updated_at timestamp
        
        # Handle optional tags conversion 
        if 'optionalTags' in data:
            data['optional_tags'] = data.pop('optionalTags', [])

        # Find the post and update it
        POSTS = get_posts_collection()
        result = POSTS.update_one(
            {'_id': ObjectId(id)},
            {'$set': data}
        )

        if result.matched_count == 0:
            return jsonify({'message': 'Post not found'}), 404

        return jsonify({'message': 'Post updated'}), 200
    
    except ValidationError as err:
        # Return error messages in case of validation failure
        return jsonify({'errors': err.messages}), 400

# DELETE (Delete a document by ID)
@posts_routes_blueprint.route('/api/posts/delete/<id>', methods=['DELETE'])
def delete_post(id):
    """
    Delete a post by ID
    ---
    parameters:
      - name: id
        in: path
        required: true
        type: string
        description: The ID of the post to delete
    responses:
      200:
        description: Post deleted
      400:
        description: Invalid post ID
      404:
        description: Post not found
    """
    try:
        # Validate the post_id to ensure it's a valid ObjectId
        if not ObjectId.is_valid(id):
            return jsonify({'error': 'Invalid post ID'}), 400

        # Find the post and delete it
        POSTS = get_posts_collection()
        result = POSTS.delete_one({'_id': ObjectId(id)})

        if result.deleted_count == 0:
            return jsonify({'message': 'Post not found'}), 404

        return jsonify({'message': 'Post deleted'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500